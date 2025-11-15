"""
Console-based test script for testing all features from main.py
This script allows interactive testing of:
- Different LLM providers (groq, openai, gemini, ollama)
- Different use cases (basic_chatbot, mcp_chatbot)
- Session management
- Tool loading and usage
"""

import os
import sys
import asyncio
from pathlib import Path
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
from langgraph_agent.nodes.mcp_chatbot_node import load_mcp_tools
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Load environment variables
load_dotenv()

# Global MCP tools (loaded once at startup)
mcp_tools = None
# In-memory session store: (session_id, use_case) -> list of LangChain messages
session_store: Dict[str, List] = {}


async def load_mcp_tools_global():
    """Load MCP tools once and cache them globally"""
    global mcp_tools
    if mcp_tools is not None:
        return mcp_tools

    try:
        tools = await load_mcp_tools()
        mcp_tools = tools
        print(f"✓ MCP tools loaded: {len(mcp_tools)} tools")
        return mcp_tools
    except Exception as e:
        print(f"✗ Error loading MCP tools: {e}")
        return []


def get_llm(provider: str, selected_llm: Optional[str] = None):
    """Get LLM instance based on provider"""
    provider = provider.lower()

    if provider == "groq":
        user_controls_input = {
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
            "selected_llm": selected_llm or "openai/gpt-oss-20b",
        }
        return GroqLLM(user_controls_input).get_base_llm()
    elif provider == "openai":
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
            "selected_llm": selected_llm or "gpt-4o-mini",
        }
        return OpenAiLLM(user_controls_input).get_base_llm()
    elif provider == "gemini":
        user_controls_input = {
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "selected_llm": selected_llm or "gemini-2.5-flash",
        }
        return GeminiLLM(user_controls_input).get_base_llm()
    elif provider == "ollama":
        user_controls_input = {
            "selected_llm": selected_llm or "gemma3:1b",
            "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        }
        return OllamaLLM(user_controls_input).get_base_llm()
    else:
        raise ValueError(f"Unsupported provider: {provider}")


async def chat(
    message: str,
    provider: str = "groq",
    use_case: str = "basic_chatbot",
    session_id: str = "default",
    selected_llm: Optional[str] = None,
):
    """Process a chat message (replicates main.py chat endpoint logic)"""
    try:
        # Get LLM
        llm = get_llm(provider, selected_llm)

        # Build graph
        graph_builder = GraphBuilder(llm, {"selected_llm": selected_llm or ""})

        # For MCP chatbot, use pre-loaded tools
        tools = None
        if use_case == "mcp_chatbot":
            tools = (
                mcp_tools if mcp_tools is not None else await load_mcp_tools_global()
            )

        graph = await graph_builder.setup_graph(use_case, tools=tools)

        # Resolve session and initialize store if needed
        session_key = f"{session_id}::{use_case}"
        if session_key not in session_store:
            session_store[session_key] = []

        # Build messages from stored history and current input
        messages = [SystemMessage(content="You are a helpful and efficient assistant.")]
        messages.extend(session_store[session_key])
        user_msg = HumanMessage(content=message)
        messages.append(user_msg)

        # Create state with all messages for context
        state = {"messages": messages}

        # Process with chatbot graph
        result = await graph.ainvoke(state)

        # Extract response
        result_messages = result.get("messages", [])
        if result_messages:
            last_message = result_messages[-1]
            if hasattr(last_message, "content"):
                response_text = last_message.content
            elif isinstance(last_message, dict) and "content" in last_message:
                response_text = last_message["content"]
            else:
                response_text = str(last_message)
        else:
            response_text = "No response generated"

        # Persist history for this session
        session_store[session_key].append(user_msg)
        session_store[session_key].append(AIMessage(content=response_text))

        return response_text

    except Exception as e:
        return f"Error: {str(e)}"


def reset_chat(session_id: str = "default", use_case: str = "basic_chatbot"):
    """Reset chat session"""
    session_key = f"{session_id}::{use_case}"
    session_store.pop(session_key, None)
    print(f"✓ Chat session '{session_key}' reset")


def print_menu():
    """Print the main menu"""
    print("\n" + "=" * 60)
    print("CONSOLE TEST MENU")
    print("=" * 60)
    print("1. Chat (Basic Chatbot)")
    print("2. Chat (MCP Chatbot with Tools)")
    print("3. Change Provider")
    print("4. Change Session ID")
    print("5. Reset Session")
    print("6. List Sessions")
    print("7. Test All Providers")
    print("8. Test MCP Tools")
    print("9. Exit")
    print("=" * 60)


async def interactive_chat(
    provider: str = "groq", use_case: str = "basic_chatbot", session_id: str = "default"
):
    """Interactive chat loop"""
    print(f"\n{'=' * 60}")
    print(f"Interactive Chat Mode")
    print(f"Provider: {provider} | Use Case: {use_case} | Session: {session_id}")
    print(f"{'=' * 60}")
    print("Type 'back' to return to menu, 'quit' to exit\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["back", "exit", "quit"]:
                break

            if not user_input:
                continue

            print("\nAssistant: ", end="", flush=True)
            response = await chat(user_input, provider, use_case, session_id)
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n\nReturning to menu...")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


async def test_all_providers():
    """Test all available providers"""
    print("\n" + "=" * 60)
    print("Testing All Providers")
    print("=" * 60)

    providers = ["groq", "openai", "gemini", "ollama"]
    test_message = "Say hello in one sentence"

    for provider in providers:
        try:
            print(f"\nTesting {provider.upper()}...")
            response = await chat(
                test_message,
                provider=provider,
                use_case="basic_chatbot",
                session_id=f"test_{provider}",
            )
            print(f"✓ {provider.upper()}: {response[:100]}...")
        except Exception as e:
            print(f"✗ {provider.upper()}: Error - {e}")

    print("\n" + "=" * 60)


async def test_mcp_tools():
    """Test MCP tools functionality"""
    print("\n" + "=" * 60)
    print("Testing MCP Tools")
    print("=" * 60)

    # Load tools if not already loaded
    if mcp_tools is None:
        await load_mcp_tools_global()

    if not mcp_tools:
        print("✗ No MCP tools available")
        return

    print(f"\nAvailable tools: {len(mcp_tools)}")
    for i, tool in enumerate(mcp_tools, 1):
        print(f"  {i}. {tool.name}")

    # Test with multiply tool
    print("\nTesting multiply tool...")
    response = await chat(
        "Use multiply tool to multiply 2 and 3",
        provider="openai",
        use_case="mcp_chatbot",
        session_id="test_mcp",
    )
    print(f"Response: {response}")


async def main():
    """Main console application"""
    print("\n" + "=" * 60)
    print("AGENTIC BASE REACT - CONSOLE TESTER")
    print("=" * 60)

    # Load MCP tools at startup
    print("\nLoading MCP tools...")
    await load_mcp_tools_global()

    # Default settings
    current_provider = "groq"
    current_use_case = "basic_chatbot"
    current_session_id = "default"

    while True:
        print_menu()
        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            await interactive_chat(
                current_provider, "basic_chatbot", current_session_id
            )

        elif choice == "2":
            await interactive_chat(current_provider, "mcp_chatbot", current_session_id)

        elif choice == "3":
            print("\nAvailable providers:")
            print("1. groq")
            print("2. openai")
            print("3. gemini")
            print("4. ollama")
            provider_choice = input("Select provider (1-4): ").strip()
            providers = {"1": "groq", "2": "openai", "3": "gemini", "4": "ollama"}
            if provider_choice in providers:
                current_provider = providers[provider_choice]
                print(f"✓ Provider set to: {current_provider}")
            else:
                print("✗ Invalid choice")

        elif choice == "4":
            new_session = input("Enter new session ID: ").strip()
            if new_session:
                current_session_id = new_session
                print(f"✓ Session ID set to: {current_session_id}")
            else:
                print("✗ Invalid session ID")

        elif choice == "5":
            reset_chat(current_session_id, current_use_case)
            print(f"✓ Session reset")

        elif choice == "6":
            print("\nActive Sessions:")
            if session_store:
                for key in session_store.keys():
                    print(f"  - {key} ({len(session_store[key])} messages)")
            else:
                print("  No active sessions")

        elif choice == "7":
            await test_all_providers()

        elif choice == "8":
            await test_mcp_tools()

        elif choice == "9":
            print("\nGoodbye!")
            break

        else:
            print("✗ Invalid choice. Please try again.")


if __name__ == "__main__":
    import nest_asyncio

    nest_asyncio.apply()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback

        traceback.print_exc()
