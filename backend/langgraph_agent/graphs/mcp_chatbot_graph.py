from langgraph.graph import START, END
from typing import List, Optional
from langchain.tools import BaseTool

from pathlib import Path
import sys

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.nodes.mcp_chatbot_node import MCPChatbotNode
from langgraph_agent.nodes.mood_detection_node import MoodDetectionNode


def mcp_chatbot_build_graph(graph_builder, llm, tools: Optional[List[BaseTool]] = None):
    """
    Builds an MCP chatbot graph using LangGraph.
    This method initializes a chatbot node using the `MCPChatbotNode` class
    with MCP tools support and integrates it into the graph. The chatbot node
    is set as both the entry and exit point of the graph.
    Also includes a mood detection node that analyzes conversation and updates mood.

    Args:
        graph_builder: The StateGraph instance to add nodes to
        llm: The language model to use for the chatbot
        tools: Optional list of tools to bind to the LLM (from MCP servers, Tavily, etc.)
    """
    # Filter out mood update tools from chatbot node (mood should only be updated by mood_detection node)
    # Also filter out patient tools (patient tools are only for doctor_chatbot)
    chatbot_tools = []
    mood_tools = []
    mood_tools_to_exclude = ["health_update_mood"]
    patient_tool_prefixes = [
        "patient_",
        "patient_search_",
        "patient_get_",
        "patient_advanced_",
    ]

    if tools:
        for tool in tools:
            tool_name = None
            if hasattr(tool, "name"):
                tool_name = tool.name
            elif isinstance(tool, dict):
                tool_name = tool.get("name")

            # Check if it's a patient tool
            is_patient_tool = tool_name and any(
                tool_name.startswith(prefix) for prefix in patient_tool_prefixes
            )

            # Exclude patient tools from both nodes
            if is_patient_tool:
                print(f"[MCP Chatbot Graph] Excluding patient tool: {tool_name}")
                continue

            # Exclude mood update tools from chatbot (but include in mood detection)
            if tool_name not in mood_tools_to_exclude:
                chatbot_tools.append(tool)

            # Mood detection node gets all non-patient tools (including mood update tools)
            mood_tools.append(tool)

    # Mood detection node gets filtered tools (no patient tools, but includes mood update tools)
    mcp_chatbot_node = MCPChatbotNode(llm, tools=chatbot_tools)
    mood_detection_node = MoodDetectionNode(llm, tools=mood_tools)

    # LangGraph can handle async nodes, so we can add the async process method directly
    graph_builder.add_node("mood_detection", mood_detection_node.process)
    graph_builder.add_node("mcp_chatbot", mcp_chatbot_node.process)

    # Flow: START -> mood_detection -> mcp_chatbot -> END
    graph_builder.add_edge(START, "mood_detection")
    graph_builder.add_edge("mood_detection", "mcp_chatbot")
    graph_builder.add_edge("mcp_chatbot", END)


if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv
    from langgraph.graph import StateGraph
    from langgraph_agent.llms.openai_llm import OpenAiLLM
    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph_agent.states.chatbotState import ChatbotState
    from langgraph_agent.nodes.mcp_chatbot_node import load_mcp_tools

    load_dotenv()

    async def main():
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

        # Create graph builder
        graph_builder = StateGraph(ChatbotState)

        # Build the graph with MCP tools
        mcp_chatbot_build_graph(graph_builder, llm, tools=tools)

        # Compile the graph
        graph = graph_builder.compile()

        # Create input state for the graph
        initial_state = {
            "messages": [
                SystemMessage(content="You are a helpful and efficient assistant."),
                HumanMessage(content="Use multiply tool to multiply 2 and 3"),
            ]
        }

        # Run the graph and print the output
        result = await graph.ainvoke(initial_state)
        print("result: ", result)
        print("\n---- Graph Result ----")
        result_messages = result.get("messages", [])
        if result_messages:
            last_message = result_messages[-1]
            if hasattr(last_message, "content"):
                print(last_message.content)
            else:
                print(result)

    # Run the async main function
    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
