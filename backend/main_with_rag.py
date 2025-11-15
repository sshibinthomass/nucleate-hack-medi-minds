import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from rag_crawler import MedicalRAGCrawler, MEDICAL_SOURCES

# Load environment variables
load_dotenv()

# Initialize RAG crawler globally
rag_crawler = None


async def initialize_rag():
    """Initialize RAG crawler on startup."""
    global rag_crawler
    try:
        rag_crawler = MedicalRAGCrawler(chroma_db_path="./medical_data_store")
        
        # Prepare URLs and source names
        urls = [source["url"] for source in MEDICAL_SOURCES.values()]
        source_names = list(MEDICAL_SOURCES.keys())
        
        # Add crawl4ai documentation
        urls.append("https://docs.crawl4ai.com/core/quickstart/")
        source_names.append("crawl4ai_docs")
        
        # Ingest data
        print("🚀 Initializing medical knowledge base...")
        await rag_crawler.ingest_medical_data(urls, source_names)
        print("✅ Medical knowledge base initialized successfully!")
        
    except Exception as e:
        print(f"❌ Error initializing RAG: {str(e)}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI."""
    # Startup
    await initialize_rag()
    yield
    # Shutdown
    print("🛑 Shutting down...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Medi-Minds RAG API",
    description="Medical AI with Retrieval Augmented Generation",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "medi-minds-rag"}


@app.post("/query")
async def query_medical_knowledge(query: str, n_results: int = 5):
    """
    Query the medical knowledge base.
    
    Args:
        query: Medical query
        n_results: Number of results to return
    """
    if not rag_crawler:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        results = rag_crawler.query_medical_knowledge(query, n_results=n_results)
        
        return {
            "query": query,
            "results_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get vector store statistics."""
    if not rag_crawler:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    return rag_crawler.get_collection_stats()


@app.post("/crawl-custom")
async def crawl_custom_urls(urls: list[str], source_names: list[str] = None):
    """
    Crawl custom URLs and add to knowledge base.
    
    Args:
        urls: List of URLs to crawl
        source_names: Optional list of source names
    """
    if not rag_crawler:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        if source_names is None:
            source_names = [f"custom_source_{i}" for i in range(len(urls))]
        
        await rag_crawler.ingest_medical_data(urls, source_names)
        
        return {
            "status": "success",
            "urls_crawled": len(urls),
            "message": "Data ingested successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)