from typing_extensions import TypedDict, List
from langgraph.graph.message import add_messages
from typing import Annotated


class ChatbotState(TypedDict):
    """
    Represent the structure of the state used in graph,
    add_messages is a function that adds messages to the state for history of the conversation
    """

    messages: Annotated[List, add_messages]
