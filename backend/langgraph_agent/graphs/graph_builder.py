from langgraph.graph import StateGraph

from pathlib import Path
import sys
import dotenv

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.states.chatbotState import (
    ChatbotState,
)  # ignoring the import error
from langgraph_agent.graphs.basic_chatbot_graph import basic_chatbot_build_graph
from langgraph_agent.graphs.mcp_chatbot_graph import mcp_chatbot_build_graph

dotenv.load_dotenv()


class GraphBuilder:
    def __init__(self, model, user_controls_input: dict):
        self.llm = model
        self.user_controls_input = user_controls_input
        self.graph_builder = StateGraph(
            ChatbotState
        )  # StateGraph is a class in LangGraph that is used to build the graph

    async def setup_graph(self, usecase: str, tools=None):
        """
        Sets up the graph for the selected use case.

        Args:
            usecase: The use case to set up ("basic_chatbot", "mcp_chatbot", etc.)
            tools: Optional list of tools for MCP chatbot
        """
        if usecase == "basic_chatbot":
            basic_chatbot_build_graph(self.graph_builder, self.llm)
        elif usecase == "mcp_chatbot":
            mcp_chatbot_build_graph(self.graph_builder, self.llm, tools=tools)
        else:
            raise ValueError(f"Unsupported use case: {usecase}")

        return self.graph_builder.compile()


if __name__ == "__main__":
    import asyncio
    from langgraph_agent.llms.openai_llm import OpenAiLLM
    from langgraph_agent.nodes.mcp_chatbot_node import load_mcp_tools
    from langchain_core.messages import HumanMessage, SystemMessage
    import os

    async def main():
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "selected_llm": "gpt-4.1-mini",
        }
        llm = OpenAiLLM(user_controls_input)
        llm = llm.get_base_llm()

        graph_builder = GraphBuilder(llm, user_controls_input)

        # For MCP chatbot, load tools first
        tools = await load_mcp_tools()
        print(f"Tools loaded: {len(tools)}")

        # Setup graph with tools
        graph = await graph_builder.setup_graph("mcp_chatbot", tools=tools)

        # Create input state for the graph
        initial_state = {
            "messages": [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(
                    content="Use preplexity to give me today's news in india?"
                ),
            ]
        }

        # Run the graph and print the output (use ainvoke for async graph)
        result = await graph.ainvoke(initial_state)
        print("result: ", result)
        print("Graph Output:", result)

    # Run the async main function
    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
