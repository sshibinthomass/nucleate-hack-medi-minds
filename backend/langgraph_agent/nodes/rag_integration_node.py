"""
RAG Integration Node for LangGraph with Auto-Initialization
This node automatically initializes the vector store if it doesn't exist
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage

# Add project root to path to find rag_crawler
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from rag_crawler import MedicalRAGCrawler
except ImportError as e:
    print(f"⚠️  Warning: Could not import MedicalRAGCrawler: {e}")
    raise


class RAGIntegrationNode:
    """
    RAG Node that retrieves medical context and augments prompts.
    Automatically initializes the vector store if it doesn't exist.
    """
    
    def __init__(
        self, 
        chroma_db_path: str = "./medical_data_store",
        auto_init: bool = True,
        min_documents: int = 10,
        lazy_init: bool = True
    ):
        """
        Initialize RAG node with ChromaDB vector store.
        
        Args:
            chroma_db_path: Path to ChromaDB storage
            auto_init: Whether to auto-initialize if database is empty
            min_documents: Minimum documents required to skip initialization
            lazy_init: If True, delay initialization until first query
        """
        self.chroma_db_path = chroma_db_path
        self.auto_init = auto_init
        self.min_documents = min_documents
        self.lazy_init = lazy_init
        self.retrieval_cache: Dict[str, List[Dict]] = {}
        self._initialized = False
        self.rag_crawler = None
        
        if not lazy_init:
            # Initialize immediately
            self._initialize_crawler()
    
    def _initialize_crawler(self):
        """Initialize the RAG crawler."""
        try:
            print(f"🔧 Initializing RAGIntegrationNode...")
            self.rag_crawler = MedicalRAGCrawler(
                chroma_db_path=self.chroma_db_path,
                auto_init=self.auto_init,
                min_documents=self.min_documents
            )
            self._initialized = True
            print(f"✅ RAGIntegrationNode initialized successfully")
            print(f"   ChromaDB path: {self.chroma_db_path}")
            print(f"   Documents: {self.rag_crawler.collection.count()}")
        except Exception as e:
            print(f"❌ Failed to initialize RAGIntegrationNode: {e}")
            raise
    
    async def ensure_ready(self) -> bool:
        """
        Ensure the RAG system is ready to use.
        Initializes crawler and database if needed.
        
        Returns:
            True if ready, False if initialization failed
        """
        if not self._initialized:
            self._initialize_crawler()
        
        if self.rag_crawler and self.auto_init:
            return await self.rag_crawler.ensure_initialized()
        
        return self._initialized
    
    async def retrieve_medical_context(
        self, 
        query: str, 
        n_results: int = 5,
        similarity_threshold: float = 0.15
    ) -> List[Dict]:
        """
        Retrieve medical context using cosine similarity.
        Automatically initializes the database if needed.
        
        Args:
            query: User question or medical query
            n_results: Number of results to retrieve
            similarity_threshold: Minimum cosine similarity score (0-1)
            
        Returns:
            List of relevant medical documents with metadata
        """
        try:
            # Ensure system is ready
            ready = await self.ensure_ready()
            if not ready:
                print(f"⚠️  RAG system not ready, returning empty results")
                return []
            
            # Check cache first
            cache_key = f"{query}_{n_results}"
            if cache_key in self.retrieval_cache:
                print(f"💾 Using cached results for query")
                return self.retrieval_cache[cache_key]
            
            # Query ChromaDB with cosine similarity
            print(f"🔍 Querying ChromaDB for: '{query[:50]}...'")
            results = self.rag_crawler.query_medical_knowledge(query, n_results)
            
            if not results:
                print(f"  No results returned from ChromaDB")
                return []
            
            print(f"📚 Retrieved {len(results)} results from ChromaDB")
            
            # Filter by similarity threshold
            filtered_results = []
            for result in results:
                distance = result.get('distance')
                if distance is not None:
                    similarity = 1 - distance
                    if similarity >= similarity_threshold:
                        filtered_results.append(result)
                        print(f"   ✓ Kept result (similarity: {similarity:.2%})")
                    else:
                        print(f"   ✗ Filtered result (similarity: {similarity:.2%} < {similarity_threshold:.2%})")
            
            if not filtered_results:
                print(f"⚠️  All results filtered out by similarity threshold ({similarity_threshold})")
            else:
                print(f"✅ {len(filtered_results)} results passed similarity threshold")
            
            # Cache results
            self.retrieval_cache[cache_key] = filtered_results
            
            return filtered_results
            
        except Exception as e:
            print(f"❌ Error in retrieve_medical_context: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def format_rag_context(self, results: List[Dict]) -> str:
        """
        Format retrieved results into a readable context string.
        
        Args:
            results: Retrieved documents from ChromaDB
            
        Returns:
            Formatted context string for LLM
        """
        if not results:
            return ""
        
        try:
            context_parts = []
            context_parts.append("\n📚 MEDICAL KNOWLEDGE BASE CONTEXT (Retrieved via Semantic Search):\n")
            context_parts.append("=" * 80)
            
            for i, result in enumerate(results, 1):
                metadata = result.get('metadata', {})
                source_name = metadata.get('source_name', 'Unknown Source')
                source_url = metadata.get('source_url', 'N/A')
                
                distance = result.get('distance', 1)
                similarity_score = 1 - distance
                
                document = result.get('document', '')
                
                context_parts.append(f"\n[Result {i}] - Similarity: {similarity_score:.2%}")
                context_parts.append(f"Source: {source_name}")
                context_parts.append(f"URL: {source_url}")
                
                # Truncate document content to first 500 chars
                doc_preview = document[:500] if len(document) > 500 else document
                context_parts.append(f"Content:\n{doc_preview}...")
                context_parts.append("-" * 80)
            
            formatted = "\n".join(context_parts)
            print(f"📝 Formatted RAG context: {len(formatted)} characters")
            return formatted
            
        except Exception as e:
            print(f"❌ Error in format_rag_context: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    async def augment_system_prompt(
        self, 
        user_query: str,
        base_system_prompt: str,
        n_results: int = 5
    ) -> Tuple[str, List[Dict]]:
        """
        Augment the system prompt with RAG context.
        
        Args:
            user_query: The user's medical question
            base_system_prompt: Original system prompt
            n_results: Number of documents to retrieve
            
        Returns:
            Tuple of (augmented_prompt, retrieved_results)
        """
        try:
            print(f"\n{'='*80}")
            print(f"RAG AUGMENTATION PROCESS")
            print(f"{'='*80}")
            print(f"User Query: {user_query[:100]}...")
            print(f"Requesting {n_results} results")
            
            # Retrieve relevant medical documents
            rag_results = await self.retrieve_medical_context(user_query, n_results)
            
            if not rag_results:
                print(f"⚠️  No RAG results to augment with")
                return base_system_prompt, []
            
            # Format context for inclusion in prompt
            rag_context = self.format_rag_context(rag_results)
            
            if not rag_context:
                print(f"⚠️  Failed to format RAG context")
                return base_system_prompt, rag_results
            
            # Augmented system prompt with RAG context
            augmented_prompt = f"""{base_system_prompt}

{rag_context}

INSTRUCTIONS FOR USING CONTEXT:
- Use the retrieved medical knowledge base context above to inform your response
- Cite specific sources when providing medical information
- If context is not sufficient, acknowledge the limitation
- Prioritize accuracy and user safety in all medical recommendations
"""
            
            print(f"✅ System prompt augmented successfully")
            print(f"   Original prompt: {len(base_system_prompt)} chars")
            print(f"   Augmented prompt: {len(augmented_prompt)} chars")
            print(f"   Added context: {len(augmented_prompt) - len(base_system_prompt)} chars")
            print(f"{'='*80}\n")
            
            return augmented_prompt, rag_results
            
        except Exception as e:
            print(f"❌ Error in augment_system_prompt: {e}")
            import traceback
            traceback.print_exc()
            return base_system_prompt, []
    
    async def create_rag_aware_state(
        self,
        state: Dict[str, Any],
        user_query: str,
        base_system_prompt: str
    ) -> Dict[str, Any]:
        """
        Transform the LangGraph state to include RAG context.
        
        Args:
            state: Original LangGraph state
            user_query: User's question
            base_system_prompt: Original system prompt
            
        Returns:
            Updated state with augmented system prompt and RAG metadata
        """
        try:
            # Get augmented prompt and retrieval results
            augmented_prompt, rag_results = await self.augment_system_prompt(
                user_query, 
                base_system_prompt
            )
            
            # Update messages with augmented system prompt
            messages = state.get("messages", [])
            
            # Replace or add system message
            new_messages = []
            system_message_found = False
            
            for msg in messages:
                if isinstance(msg, SystemMessage):
                    # Replace with augmented version
                    new_messages.append(SystemMessage(content=augmented_prompt))
                    system_message_found = True
                else:
                    new_messages.append(msg)
            
            # If no system message exists, add one
            if not system_message_found:
                new_messages.insert(0, SystemMessage(content=augmented_prompt))
            
            # Create updated state
            updated_state = state.copy()
            updated_state["messages"] = new_messages
            updated_state["rag_context"] = {
                "query": user_query,
                "results_count": len(rag_results),
                "results": rag_results,
                "augmented_prompt": augmented_prompt
            }
            
            return updated_state
            
        except Exception as e:
            print(f"❌ Error in create_rag_aware_state: {e}")
            import traceback
            traceback.print_exc()
            return state


class RAGChatbotNode:
    """
    Complete RAG Chatbot Node with LLM invocation and auto-initialization.
    """
    
    def __init__(
        self, 
        model, 
        rag_integration_node: Optional[RAGIntegrationNode] = None,
        chroma_db_path: str = "./medical_data_store"
    ):
        """
        Initialize the RAG chatbot node with LLM and RAG.
        
        Args:
            model: The language model to use
            rag_integration_node: RAGIntegrationNode instance (creates one if None)
            chroma_db_path: Path to ChromaDB (used if creating new RAG node)
        """
        self.llm = model
        
        if rag_integration_node is None:
            print(f"🔧 Creating new RAGIntegrationNode...")
            self.rag_node = RAGIntegrationNode(
                chroma_db_path=chroma_db_path,
                auto_init=True,
                lazy_init=True  # Will initialize on first use
            )
        else:
            self.rag_node = rag_integration_node
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the state: retrieve RAG context, augment prompt, call LLM.
        
        Args:
            state: LangGraph state with 'messages' key
            
        Returns:
            Updated state with AI response and RAG metadata
        """
        try:
            # Create a copy of messages
            messages = list(state.get("messages", []))
            
            # Extract user query from most recent human message
            user_query = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    user_query = msg.content
                    break
            
            # Default system prompt
            base_system_prompt = "You are Medi-Mind, a personal medical assistant. You help users manage their medical details, track health information, answer medical questions, and provide health-related guidance. Always be empathetic, professional, and prioritize user safety. Remind users that you are not a substitute for professional medical advice."
            
            # Get existing system prompt if available
            for msg in messages:
                if isinstance(msg, SystemMessage):
                    base_system_prompt = msg.content
                    break
            
            # RAG Integration: Retrieve and augment
            rag_context_used = False
            rag_results = []
            
            if self.rag_node is not None and user_query:
                try:
                    print(f"📚 RAG: Retrieving medical context...")
                    print(f"   Query: {user_query[:100]}...")
                    
                    # Augment system prompt with RAG context
                    augmented_prompt, rag_results = await self.rag_node.augment_system_prompt(
                        user_query,
                        base_system_prompt,
                        n_results=5
                    )
                    
                    if rag_results:
                        rag_context_used = True
                        print(f"✅ RAG: Retrieved {len(rag_results)} relevant sources")
                        for i, result in enumerate(rag_results, 1):
                            source_name = result.get('metadata', {}).get('source_name', 'Unknown')
                            similarity = 1 - result.get('distance', 1)
                            print(f"   [{i}] {source_name} (Similarity: {similarity:.2%})")
                        
                        # Replace or add system message with RAG-augmented version
                        new_messages = []
                        system_message_found = False
                        
                        for msg in messages:
                            if isinstance(msg, SystemMessage):
                                new_messages.append(SystemMessage(content=augmented_prompt))
                                system_message_found = True
                            else:
                                new_messages.append(msg)
                        
                        if not system_message_found:
                            new_messages.insert(0, SystemMessage(content=augmented_prompt))
                        
                        messages = new_messages
                    else:
                        print(f"ℹ️  RAG: No relevant context found")
                        
                except Exception as e:
                    print(f"⚠️  RAG retrieval failed: {e}")
                    if not any(isinstance(msg, SystemMessage) for msg in messages):
                        messages = [SystemMessage(content=base_system_prompt)] + messages
            else:
                if not any(isinstance(msg, SystemMessage) for msg in messages):
                    messages = [SystemMessage(content=base_system_prompt)] + messages
            
            # Call LLM with (potentially augmented) messages
            print(f"🤖 Invoking LLM with {'RAG-augmented' if rag_context_used else 'standard'} context...")
            response = self.llm.invoke(messages)
            
            # Ensure response is an AIMessage
            if not isinstance(response, AIMessage):
                if hasattr(response, "content"):
                    response = AIMessage(content=response.content)
                elif isinstance(response, dict) and "content" in response:
                    response = AIMessage(content=response["content"])
                else:
                    response = AIMessage(content=str(response))
            
            print(f"✅ Response generated successfully")
            if hasattr(response, "content"):
                print(f"   Length: {len(response.content)} characters")
            
            # Return response with RAG metadata
            result = {"messages": [response]}
            
            if rag_context_used:
                result["rag_context"] = {
                    "query": user_query,
                    "results_count": len(rag_results),
                    "results": rag_results
                }
            
            return result
            
        except Exception as e:
            print(f"❌ Error in RAGChatbotNode.process: {e}")
            import traceback
            traceback.print_exc()
            # Return error message
            return {
                "messages": [AIMessage(content=f"Error processing request: {str(e)}")]
            }


# Example usage
if __name__ == "__main__":
    print(f"\n{'='*80}")
    print(f"TESTING RAG INTEGRATION NODE WITH AUTO-INIT")
    print(f"{'='*80}\n")
    
    async def test_rag_node():
        # Create RAG node with auto-init
        rag_node = RAGIntegrationNode(
            chroma_db_path="./medical_data_store",
            auto_init=True,
            lazy_init=False  # Initialize immediately for testing
        )
        
        # Wait for initialization
        ready = await rag_node.ensure_ready()
        print(f"\n{'='*80}")
        print(f"RAG Node Ready: {ready}")
        print(f"{'='*80}\n")
        
        if ready:
            # Test query
            query = "What are the symptoms of diabetes?"
            print(f"Testing query: {query}\n")
            
            results = await rag_node.retrieve_medical_context(query, n_results=3)
            
            print(f"\n✅ Retrieved {len(results)} results")
            for i, result in enumerate(results, 1):
                metadata = result.get('metadata', {})
                similarity = 1 - result.get('distance', 1)
                print(f"  [{i}] {metadata.get('source_name')} (Similarity: {similarity:.2%})")
    
    asyncio.run(test_rag_node())