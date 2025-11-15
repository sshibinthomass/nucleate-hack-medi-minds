import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.graphs.graph_builder import GraphBuilder
from langgraph_agent.llms.groq_llm import GroqLLM
from langgraph_agent.llms.openai_llm import OpenAiLLM
from langgraph_agent.llms.gemini_llm import GeminiLLM
from langgraph_agent.llms.ollama_llm import OllamaLLM
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Load environment variables
load_dotenv()

# Global chatbot graph instance
chatbot_graph = None
# Global MCP tools (loaded once at startup)
mcp_tools = None
# In-memory session store: (session_id, use_case) -> list of LangChain messages
session_store: Dict[str, List] = {}


async def load_mcp_tools():
    """
    Load MCP tools once at startup. This function caches the tools
    so they're only loaded once and reused for all requests.
    Returns the list of tools that can be reused.
    """
    global mcp_tools
    if mcp_tools is not None:
        return mcp_tools  # Return cached tools if already loaded

    try:
        from langgraph_agent.nodes.mcp_chatbot_node import load_mcp_tools as load_tools

        # Load tools using the function from mcp_chatbot_node
        tools = await load_tools()

        mcp_tools = tools
        print(f"MCP tools loaded: {len(mcp_tools)} tools")
        return mcp_tools
    except Exception as e:
        print(f"Error loading MCP tools: {e}")
        return []


async def initialize_chatbot():
    """Initialize the chatbot graph with OpenAI LLM"""
    global chatbot_graph
    try:
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "selected_llm": "gpt-4o-mini",
        }
        llm = OpenAiLLM(user_controls_input)
        llm = llm.get_base_llm()
        graph_builder = GraphBuilder(llm, user_controls_input)
        # Load MCP tools for initialization
        tools = await load_mcp_tools()
        chatbot_graph = await graph_builder.setup_graph("mcp_chatbot", tools=tools)
        return True
    except Exception as e:
        print(f"Error initializing chatbot: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    # Load MCP tools once at startup
    await load_mcp_tools()

    if not await initialize_chatbot():
        print(
            "Warning: Failed to initialize chatbot. API will still work but chatbot endpoints may fail."
        )
    yield
    # Shutdown (if needed, add cleanup code here)
    # For example: cleanup resources, close connections, etc.


# Initialize FastAPI app
app = FastAPI(
    title="Medi-Mind Backend",
    description="FastAPI backend for the Medi-Mind medical assistant application",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


class SimpleChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    provider: Optional[str] = "openai"  # groq | openai | gemini | ollama
    selected_llm: Optional[str] = None
    use_case: Optional[str] = "mcp_chatbot"


class ResetChatRequest(BaseModel):
    session_id: Optional[str] = "default"
    use_case: Optional[str] = "mcp_chatbot"


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Medi-Mind Backend API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "chatbot_initialized": chatbot_graph is not None}


@app.post("/chat", response_model=ChatResponse)
async def chat_simple(request: SimpleChatRequest):
    """
    Simple chat endpoint that takes a message.
    Conversation history is maintained on the backend per session_id.
    """
    if chatbot_graph is None:
        # Even if global init failed, we can still serve requests if provider creds are valid
        # so don't hard error here.
        pass

    try:
        # Choose LLM based on provider/model from request
        print("request-----", request)
        provider = (request.provider or "openai").lower()
        selected_llm = request.selected_llm
        if provider == "groq":
            user_controls_input = {
                "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
                "selected_llm": selected_llm or "openai/gpt-oss-20b",
            }
            llm = GroqLLM(user_controls_input).get_base_llm()
        elif provider == "openai":
            user_controls_input = {
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "selected_llm": selected_llm or "gpt-4o-mini",
            }
            llm = OpenAiLLM(user_controls_input).get_base_llm()
        elif provider == "gemini":
            user_controls_input = {
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                "selected_llm": selected_llm or "gemini-2.5-flash",
            }
            llm = GeminiLLM(user_controls_input).get_base_llm()
        elif provider == "ollama":
            user_controls_input = {
                "selected_llm": selected_llm or "gemma3:1b",
                "OLLAMA_BASE_URL": os.getenv(
                    "OLLAMA_BASE_URL", "http://localhost:11434"
                ),
            }
            llm = OllamaLLM(user_controls_input).get_base_llm()
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported provider: {provider}"
            )

        use_case = request.use_case or "mcp_chatbot"

        # Build a lightweight graph for this request with the chosen LLM
        try:
            graph_builder = GraphBuilder(llm, {"selected_llm": selected_llm or ""})

            # Use pre-loaded MCP tools (loaded once at startup)
            tools = mcp_tools if mcp_tools is not None else await load_mcp_tools()

            graph = await graph_builder.setup_graph(use_case, tools=tools)
        except ValueError as graph_error:
            raise HTTPException(status_code=400, detail=str(graph_error))

        # Resolve session and initialize store if needed
        session_id = request.session_id or "default"
        session_key = f"{session_id}::{use_case}"
        if session_key not in session_store:
            session_store[session_key] = []

        # Build messages from stored history and current input
        messages = [SystemMessage(content="You are Medi-Mind, a personal medical assistant. You help users manage their medical details, track health information, answer medical questions, and provide health-related guidance. Always be empathetic, professional, and prioritize user safety. Remind users that you are not a substitute for professional medical advice.")]
        messages.extend(session_store[session_key])
        user_msg = HumanMessage(content=request.message)
        messages.append(user_msg)

        # Create state with all messages for context
        state = {"messages": messages}
        print("state-----", state)
        # Process with chatbot graph (use ainvoke for async graphs)
        result = await graph.ainvoke(state)
        # Extract response from graph result
        # The graph returns a state dict with messages, get the last message (should be AI response)
        result_messages = result.get("messages", [])
        if result_messages:
            last_message = result_messages[-1]
            # Extract content if it's a message object
            if hasattr(last_message, "content"):
                response_text = last_message.content
            elif isinstance(last_message, dict) and "content" in last_message:
                response_text = last_message["content"]
            else:
                response_text = str(last_message)
        else:
            response_text = "No response generated"

        # Persist history for this session (user + assistant)
        session_store[session_key].append(user_msg)
        session_store[session_key].append(AIMessage(content=response_text))

        return ChatResponse(response=response_text, status="success")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing chat request: {str(e)}"
        )


@app.post("/chat/reset")
async def reset_chat(request: ResetChatRequest):
    session_id = request.session_id or "default"
    use_case = request.use_case or "mcp_chatbot"
    session_key = f"{session_id}::{use_case}"
    session_store.pop(session_key, None)
    return {"status": "success"}


def main():
    """Main function to run the FastAPI server"""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
