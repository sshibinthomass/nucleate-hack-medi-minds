import asyncio
import os
from typing import List, Dict, Optional
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
import chromadb
from chromadb.config import Settings
import hashlib
from datetime import datetime

# Medical data sources configuration
MEDICAL_SOURCES = {
    "pubmed": {
        "url": "https://pubmed.ncbi.nlm.nih.gov/",
        "description": "Massive database of biomedical and life sciences literature",
        "use_case": "Crawling abstracts and full-text articles for latest research on diseases, symptoms, diagnostics, and treatments"
    },
    "medlineplus": {
        "url": "https://medlineplus.gov/",
        "description": "Consumer health information from U.S. National Library of Medicine",
        "use_case": "Well-vetted, patient-friendly disease and symptom descriptions"
    },
    "hpo": {
        "url": "https://hpo.jax.org/app/",
        "description": "Standardized vocabulary of phenotypic abnormalities (symptoms)",
        "use_case": "Query symptoms with precise ontology codes; link phenotypes to diseases"
    },
    "disease_ontology": {
        "url": "https://disease-ontology.org/",
        "description": "Standardized disease vocabulary, cross-referenced to other vocabularies",
        "use_case": "Backbone for disease terms; link to symptoms and treatments"
    },
    "clinical_trials": {
        "url": "https://clinicaltrials.gov/",
        "description": "Registry of clinical studies worldwide",
        "use_case": "Extract disease info, symptoms tracked, drug trials, and interventions"
    },
    "rxnorm": {
        "url": "https://www.nlm.nih.gov/research/umls/rxnorm/",
        "description": "Normalized names for clinical drugs and vocabularies",
        "use_case": "Link symptoms and diseases to drug treatments"
    },
    "who_icd11": {
        "url": "https://icd.who.int/en",
        "description": "International Classification of Diseases 11th Revision",
        "use_case": "Standardized disease codes, definitions, and symptom classifications"
    },
    "openfda": {
        "url": "https://open.fda.gov/apis/",
        "description": "FDA datasets (drug adverse events, recalls, labeling)",
        "use_case": "Drug safety info complementing disease and symptom data"
    }
}


class MedicalRAGCrawler:
    def __init__(self, chroma_db_path: str = "./medical_data_store", auto_init: bool = True, min_documents: int = 10):
        """
        Initialize the Medical RAG Crawler with ChromaDB vector store.
        
        Args:
            chroma_db_path: Path to store ChromaDB data
            auto_init: If True, automatically initialize database if empty
            min_documents: Minimum number of documents required to skip initialization
        """
        self.chroma_db_path = chroma_db_path
        self.auto_init = auto_init
        self.min_documents = min_documents
        os.makedirs(chroma_db_path, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=chroma_db_path)
        self.collection = self.client.get_or_create_collection(
            name="medical_knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"📊 Current database stats: {self.collection.count()} documents")
        
    def needs_initialization(self) -> bool:
        """Check if the database needs to be initialized."""
        count = self.collection.count()
        needs_init = count < self.min_documents
        
        if needs_init:
            print(f"⚠️  Database has only {count} documents (minimum: {self.min_documents})")
            print(f"   Initialization required")
        else:
            print(f"✅ Database already populated with {count} documents")
            print(f"   Skipping initialization")
        
        return needs_init
    
    async def ensure_initialized(self) -> bool:
        """
        Ensure the database is initialized. If empty and auto_init is True,
        automatically crawl and populate data.
        
        Returns:
            True if database is ready, False if initialization failed
        """
        if not self.needs_initialization():
            return True
        
        if not self.auto_init:
            print(f"❌ Database not initialized and auto_init is False")
            return False
        
        print(f"🚀 Auto-initializing medical knowledge base...")
        
        try:
            # Prepare URLs and source names
            urls = [source["url"] for source in MEDICAL_SOURCES.values()]
            source_names = list(MEDICAL_SOURCES.keys())
            
            # Add crawl4ai documentation
            urls.append("https://docs.crawl4ai.com/core/quickstart/")
            source_names.append("crawl4ai_docs")
            
            # Ingest data
            await self.ingest_medical_data(urls, source_names)
            
            # Verify initialization
            if self.collection.count() >= self.min_documents:
                print(f"✅ Database initialized successfully with {self.collection.count()} documents")
                return True
            else:
                print(f"⚠️  Initialization completed but document count is still low: {self.collection.count()}")
                return True  # Still return True as we attempted initialization
                
        except Exception as e:
            print(f"❌ Failed to initialize database: {str(e)}")
            return False
    
    async def crawl_parallel_sources(self, urls: List[str], stream: bool = True) -> List[Dict]:
        """
        Crawl multiple medical sources in parallel using AsyncWebCrawler.
        
        Args:
            urls: List of URLs to crawl
            stream: Whether to stream results as they complete
            
        Returns:
            List of crawled results with metadata
        """
        results = []
        
        run_conf = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            stream=stream,
            word_count_threshold=100
        )
        
        async with AsyncWebCrawler() as crawler:
            if stream:
                # Stream results as they complete
                print("🔄 Streaming crawl results...")
                async for result in await crawler.arun_many(urls, config=run_conf):
                    processed_result = self._process_crawl_result(result)
                    if processed_result:
                        results.append(processed_result)
                        print(f"[OK] {result.url}")
                    else:
                        print(f"[ERROR] {result.url} => {result.error_message}")
            else:
                # Get all results at once
                print("⏳ Fetching all results...")
                run_conf = run_conf.clone(stream=False)
                crawl_results = await crawler.arun_many(urls, config=run_conf)
                for result in crawl_results:
                    processed_result = self._process_crawl_result(result)
                    if processed_result:
                        results.append(processed_result)
                        print(f"[OK] {result.url}")
                    else:
                        print(f"[ERROR] {result.url} => {result.error_message}")
        
        return results
    
    def _process_crawl_result(self, result) -> Optional[Dict]:
        """
        Process and validate crawl result.
        
        Args:
            result: Crawl result object
            
        Returns:
            Processed result dictionary or None if invalid
        """
        if not result.success:
            return None
        
        return {
            "url": result.url,
            "markdown": result.markdown.raw_markdown if result.markdown else "",
            "html": result.html if hasattr(result, 'html') else "",
            "success": result.success,
            "status_code": result.status_code if hasattr(result, 'status_code') else None,
            "timestamp": datetime.now().isoformat()
        }
    
    async def ingest_medical_data(self, urls: List[str], source_names: List[str]) -> None:
        """
        Crawl medical sources and ingest data into ChromaDB.
        
        Args:
            urls: List of URLs to crawl
            source_names: List of source names corresponding to URLs
        """
        print(f"Starting to crawl {len(urls)} medical sources...\n")
        
        # Crawl all URLs in parallel
        crawled_data = await self.crawl_parallel_sources(urls, stream=True)
        
        print(f"\nProcessing {len(crawled_data)} crawled sources into vector store...\n")
        
        # Process and store in ChromaDB
        documents = []
        metadatas = []
        ids = []
        
        for i, data in enumerate(crawled_data):
            if not data["markdown"]:
                continue
            
            # Split content into chunks for better retrieval
            chunks = self._chunk_text(data["markdown"], chunk_size=1000, overlap=200)
            
            for j, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{data['url']}-{j}".encode()).hexdigest()
                
                documents.append(chunk)
                ids.append(doc_id)
                metadatas.append({
                    "source_url": data["url"],
                    "source_name": source_names[i] if i < len(source_names) else "unknown",
                    "chunk_index": j,
                    "total_chunks": len(chunks),
                    "crawled_at": data["timestamp"]
                })
        
        # Add to ChromaDB
        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"✅ Stored {len(documents)} document chunks in vector store\n")
        else:
            print("⚠️ No valid documents to store\n")
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for better retrieval.
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        chunks = []
        step = chunk_size - overlap
        
        for i in range(0, len(text), step):
            chunks.append(text[i:i + chunk_size])
        
        return chunks
    
    def query_medical_knowledge(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Query the medical knowledge base using semantic search.
        
        Args:
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of relevant documents with scores
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        formatted_results = []
        if results['documents'] and len(results['documents']) > 0:
            for i, doc in enumerate(results['documents'][0]):
                formatted_results.append({
                    "document": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else None
                })
        
        return formatted_results
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the stored collection."""
        return {
            "total_documents": self.collection.count(),
            "collection_name": self.collection.name
        }


async def main_rag_pipeline():
    """
    Main RAG pipeline: crawl medical sources and populate vector store.
    """
    # Initialize RAG crawler with auto-init enabled
    rag_crawler = MedicalRAGCrawler(auto_init=True, min_documents=10)
    
    # Ensure initialized (will skip if already populated)
    initialized = await rag_crawler.ensure_initialized()
    
    if not initialized:
        print("❌ Failed to initialize RAG crawler")
        return
    
    # Display collection stats
    stats = rag_crawler.get_collection_stats()
    print(f"\n📊 Collection Stats: {stats}\n")
    
    # Example queries
    example_queries = [
        "What are the latest treatments for diabetes?",
        "How are symptoms classified in medical ontologies?",
        "What clinical trials are available for cardiovascular diseases?",
        "Tell me about drug interactions and side effects"
    ]
    
    print("🔍 Running example queries on the medical knowledge base:\n")
    for query in example_queries:
        print(f"Q: {query}")
        results = rag_crawler.query_medical_knowledge(query, n_results=3)
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"\n  Result {i}:")
                print(f"  Source: {result['metadata'].get('source_name', 'Unknown')}")
                print(f"  URL: {result['metadata'].get('source_url', 'N/A')}")
                print(f"  Distance: {result['distance']:.4f}")
                print(f"  Content: {result['document'][:200]}...")
        else:
            print("  No results found")
        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    # Run the main RAG pipeline
    asyncio.run(main_rag_pipeline())