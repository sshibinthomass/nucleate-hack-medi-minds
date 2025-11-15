"""
This file implements the MCP Client for our Langgraph Agent.

MCP Clients are responsible for connecting and communicating with MCP servers.
This client is analagous to Cursor or Claude Desktop and you would configure them in the
same way by specifying the MCP server configuration in my_mcp/mcp_config.json.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, AIMessageChunk
from langchain_core.tools import StructuredTool
from typing import AsyncGenerator
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv
import os


from pathlib import Path
import sys

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.mcps.config import mcp_config
from langgraph_agent.graph import build_agent_graph, AgentState

load_dotenv()


async def stream_graph_response(
    input: AgentState, graph: StateGraph, config: dict = {}
) -> AsyncGenerator[str, None]:
    """
    Stream the response from the graph while parsing out tool calls.

    Args:
        input: The input for the graph.
        graph: The graph to run.
        config: The config to pass to the graph. Required for memory.

    Yields:
        A processed string from the graph's chunked response.
    """
    async for message_chunk, metadata in graph.astream(
        input=input, stream_mode="messages", config=config
    ):
        if isinstance(message_chunk, AIMessageChunk):
            if message_chunk.response_metadata:
                finish_reason = message_chunk.response_metadata.get("finish_reason", "")
                if finish_reason == "tool_calls":
                    yield "\n\n"

            if message_chunk.tool_call_chunks:
                tool_chunk = message_chunk.tool_call_chunks[0]

                tool_name = tool_chunk.get("name", "")
                args = tool_chunk.get("args", "")

                if tool_name:
                    tool_call_str = f"\n\n< TOOL CALL: {tool_name} >\n\n"
                if args:
                    tool_call_str = args

                yield tool_call_str
            else:
                yield message_chunk.content
            continue


async def main():
    """
    Initialize the MCP client and run the agent conversation loop.

    The MultiServerMCPClient allows connection to multiple MCP servers using a single client and config.
    """

    def multiply(a: int, b: int) -> int:
        """Multiply a and b.

        Args:
            a: first int
            b: second int
        """
        return a * b

    client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
    # the get_tools() method returns a list of tools from all the connected servers
    tools = await client.get_tools()

    # Add Tavily search tool if API key is available
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if tavily_api_key:
        tools.append(TavilySearchResults(max_results=5, tavily_api_key=tavily_api_key))

    # Convert multiply function to a LangChain tool
    multiply_tool = StructuredTool.from_function(multiply)
    tools.append(multiply_tool)
    print("tools: ", tools)
    graph = build_agent_graph(tools=tools)

    # pass a config with a thread_id to use memory
    graph_config = {"configurable": {"thread_id": "1"}}

    while True:
        user_input = input("\n\nUSER: ")
        if user_input in ["quit", "exit"]:
            break

        print("\n ----  USER  ---- \n\n", user_input)
        print("\n ----  ASSISTANT  ---- \n\n")

        async for response in stream_graph_response(
            input=AgentState(messages=[HumanMessage(content=user_input)]),
            graph=graph,
            config=graph_config,
        ):
            print(response, end="", flush=True)


if __name__ == "__main__":
    import asyncio

    # only needed if running in an ipykernel
    import nest_asyncio

    nest_asyncio.apply()

    asyncio.run(main())
