import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional
from langchain.tools import BaseTool
from langchain_core.messages import SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.states.chatbotState import ChatbotState
from langgraph_agent.prompts import get_scout_system_prompt
from langgraph_agent.mcps.config import mcp_config

load_dotenv()


class MCPChatbotNode:
    """
    MCP Chatbot node implementation with tool support.
    Supports MCP tools and other LangChain tools similar to graph.py and client.py.
    Handles tool calls by executing them and returning results.
    """

    def __init__(self, model, tools: Optional[List[BaseTool]] = None):
        """
        Initialize the chatbot node with an LLM and optional tools.

        Args:
            model: The language model to use
            tools: Optional list of tools to bind to the LLM (from MCP servers, Tavily, etc.)
        """
        self.llm = model
        self.tools = tools or []
        self.tool_node = ToolNode(self.tools) if self.tools else None

        # Bind tools to LLM if provided (similar to graph.py)
        if self.tools:
            self.llm = self.llm.bind_tools(self.tools)

    async def process(self, state: ChatbotState) -> dict:
        """
        Processes the input state and generates a chatbot response.
        Returns the AI response as an AIMessage object to maintain conversation history.
        If tools are available, includes system prompt similar to graph.py.
        Handles tool calls by executing them and getting the final response.
        Supports multiple rounds of tool calls if needed.
        """
        # Create a copy of messages to avoid modifying the input state
        messages = list(state["messages"])

        # Add system prompt if tools are available and not already present
        if self.tools:
            # Use the Scout system prompt when tools are available (like in graph.py)
            system_prompt = get_scout_system_prompt(
                working_dir=os.environ.get("MCP_FILESYSTEM_DIR", ""),
            )
            # Prepend system message if not already present
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [SystemMessage(content=system_prompt)] + messages

        # Handle tool calls in a loop (in case multiple rounds are needed)
        max_tool_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_tool_iterations:
            iteration += 1

            # Get response from LLM
            response = self.llm.invoke(messages)

            # Ensure response is an AIMessage
            if not isinstance(response, AIMessage):
                if hasattr(response, "content") and hasattr(response, "type"):
                    response = AIMessage(content=response.content)
                elif isinstance(response, dict) and "content" in response:
                    response = AIMessage(content=response["content"])
                elif isinstance(response, str):
                    response = AIMessage(content=response)
                else:
                    response = AIMessage(content=str(response))

            # Check if response has tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                # Display tool call information (similar to client.py)
                print("\n\n< TOOL CALLS DETECTED >\n")

                for tool_call in response.tool_calls:
                    # Handle both dict and object-style tool calls
                    # LangChain ToolCall objects have: id, name, args attributes
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name", "unknown")
                        tool_args = tool_call.get("args", {})
                        tool_id = tool_call.get("id", "")
                    else:
                        # Handle ToolCall objects with attributes (LangChain format)
                        tool_name = getattr(tool_call, "name", "unknown")
                        tool_id = getattr(tool_call, "id", "")

                        # Get args - could be attribute, method, or in __dict__
                        tool_args = {}
                        if hasattr(tool_call, "args"):
                            args_val = tool_call.args
                            # args might be a dict, string, or other type
                            if isinstance(args_val, dict):
                                tool_args = args_val
                            elif isinstance(args_val, str):
                                try:
                                    import json

                                    tool_args = json.loads(args_val)
                                except (json.JSONDecodeError, ValueError):
                                    tool_args = {"raw": args_val}
                            elif args_val is not None:
                                tool_args = args_val

                        # Also try to get from __dict__ if available
                        if not tool_args and hasattr(tool_call, "__dict__"):
                            tool_args = tool_call.__dict__.get("args", {})

                    print(f"< TOOL CALL: {tool_name} >")
                    if tool_id:
                        print(f"Tool ID: {tool_id}")
                    if tool_args:
                        print(f"Arguments: {tool_args}")
                    else:
                        print("Arguments: (none)")
                    print()

                # Add the AI response with tool calls to messages
                messages.append(response)

                # Execute tools using ToolNode (similar to graph.py)
                # Use ainvoke for async tools (MCP tools require async)
                if self.tool_node:
                    tool_state = {"messages": messages}
                    tool_result = await self.tool_node.ainvoke(tool_state)
                    tool_messages = tool_result.get("messages", [])
                    messages.extend(tool_messages)

                # Continue loop to get final response after tool execution
                continue

            # No tool calls, return the response
            return {"messages": [response]}

        # If we've exceeded max iterations, return the last response
        return {"messages": [response]}


async def load_mcp_tools():
    """
    Load MCP tools. This function sets up MCP client,
    gets tools from MCP servers, and adds Tavily and custom tools.
    Returns the list of tools.
    """
    # Set up MCP client and get tools (same as client.py)
    client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
    # the get_tools() method returns a list of tools from all the connected servers
    tools = await client.get_tools()

    # Add Tavily search tool if API key is available
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if tavily_api_key:
        tools.append(TavilySearchResults(max_results=5, tavily_api_key=tavily_api_key))

    # Convert multiply function to a LangChain tool
    def multiply(a: int, b: int) -> int:
        """Multiply a and b.

        Args:
            a: first int
            b: second int
        """
        return a * b

    multiply_tool = StructuredTool.from_function(multiply)
    tools.append(multiply_tool)

    return tools


if __name__ == "__main__":
    import asyncio
    from langgraph_agent.llms.openai_llm import OpenAiLLM
    from langchain_core.messages import HumanMessage, SystemMessage

    async def main():
        """
        Initialize the MCP chatbot node and run the agent conversation loop.
        Similar to client.py but using the MCPChatbotNode directly.
        """
        # Create LLM instance
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "selected_llm": "gpt-4.1-mini",
        }
        llm = OpenAiLLM(user_controls_input)
        llm = llm.get_base_llm()

        # Load MCP tools
        tools = await load_mcp_tools()
        print(f"Tools loaded: {len(tools)}")

        # Create MCPChatbotNode instance with tools
        node = MCPChatbotNode(llm, tools=tools)

        # Default example
        user_input = "Use preplexity to give me today's news in india?"
        print("\n ----  USER  ---- \n\n", user_input)
        print("\n ----  ASSISTANT  ---- \n\n")

        # Create state with user message
        state = {
            "messages": [
                SystemMessage(content="You are a helpful and efficient assistant."),
                HumanMessage(content=user_input),
            ]
        }

        # Process with the node (now async)
        result = await node.process(state)

        # Extract and display the response
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

            # Print the response
            print(response_text)
        else:
            print("No response generated")

    # Run the async main function
    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
