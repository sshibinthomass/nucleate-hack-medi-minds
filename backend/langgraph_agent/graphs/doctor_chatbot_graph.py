from langgraph.graph import START, END
from typing import List, Optional
from langchain.tools import BaseTool

from pathlib import Path
import sys

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.nodes.doctor_chatbot_node import DoctorChatbotNode


def doctor_chatbot_build_graph(graph_builder, llm, tools: Optional[List[BaseTool]] = None):
    """
    Builds a doctor chatbot graph using LangGraph.
    This method initializes a chatbot node using the `DoctorChatbotNode` class
    with patient specialist tools and Gmail tools support and integrates it into the graph.
    The chatbot node is set as both the entry and exit point of the graph.

    Args:
        graph_builder: The StateGraph instance to add nodes to
        llm: The language model to use for the chatbot
        tools: Optional list of tools to bind to the LLM (patient specialist tools and Gmail only)
    """
    # Doctor chatbot node gets patient tools and Gmail tools
    doctor_chatbot_node = DoctorChatbotNode(llm, tools=tools)

    # LangGraph can handle async nodes, so we can add the async process method directly
    graph_builder.add_node("doctor_chatbot", doctor_chatbot_node.process)

    # Flow: START -> doctor_chatbot -> END
    graph_builder.add_edge(START, "doctor_chatbot")
    graph_builder.add_edge("doctor_chatbot", END)


if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv
    from langgraph.graph import StateGraph
    from langgraph_agent.llms.openai_llm import OpenAiLLM
    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph_agent.states.chatbotState import ChatbotState
    from langgraph_agent.nodes.doctor_chatbot_node import load_doctor_chatbot_tools

    load_dotenv()

    async def main():
        # Create LLM instance
        user_controls_input = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "selected_llm": "gpt-4.1-mini",
        }
        llm = OpenAiLLM(user_controls_input)
        llm = llm.get_base_llm()

        # Load doctor chatbot tools (patient and Gmail only)
        tools = await load_doctor_chatbot_tools()
        print(f"Tools loaded: {len(tools)}")

        # Create graph builder
        graph_builder = StateGraph(ChatbotState)

        # Build the graph with doctor chatbot tools
        doctor_chatbot_build_graph(graph_builder, llm, tools=tools)

        # Compile the graph
        graph = graph_builder.compile()

        # Create input state for the graph
        initial_state = {
            "messages": [
                SystemMessage(content="You are a medical assistant for doctors."),
                HumanMessage(content="Search for patients with diabetes"),
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

