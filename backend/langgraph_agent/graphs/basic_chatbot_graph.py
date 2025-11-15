from langgraph.graph import START, END

from pathlib import Path
import sys

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.nodes.basic_chatbot_node import BasicChatbotNode


def basic_chatbot_build_graph(graph_builder, llm):
    """
    Builds a basic chatbot graph using LangGraph.
    This method initializes a chatbot node using the `BasicChatbotNode` class
    and integrates it into the graph. The chatbot node is set as both the
    entry and exit point of the graph.

    Args:
        graph_builder: The StateGraph instance to add nodes to
        llm: The language model to use for the chatbot
    """
    basic_chatbot_node = BasicChatbotNode(llm)

    graph_builder.add_node("chatbot", basic_chatbot_node.process)
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", END)
