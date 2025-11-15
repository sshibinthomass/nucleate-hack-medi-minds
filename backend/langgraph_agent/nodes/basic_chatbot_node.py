import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_agent.states.chatbotState import ChatbotState
from langchain_core.messages import AIMessage

load_dotenv()


class BasicChatbotNode:
    """
    Basic Chatbot login implementation
    """

    def __init__(self, model):
        self.llm = model

    def process(self, state: ChatbotState) -> dict:
        """
        Processes the input state and generates a chatbot response.
        Returns the AI response as an AIMessage object to maintain conversation history.
        """
        response = self.llm.invoke(state["messages"])

        # Error handling for the response
        # If response is already an AIMessage, return it directly
        if hasattr(response, "content") and hasattr(response, "type"):
            # It's already a message object (AIMessage)
            return {"messages": [response]}
        # If response is a dict with 'content', create AIMessage
        if isinstance(response, dict) and "content" in response:
            return {"messages": [AIMessage(content=response["content"])]}
        # If response is a string, wrap it in AIMessage
        if isinstance(response, str):
            return {"messages": [AIMessage(content=response)]}
        # Fallback: try to extract content and create AIMessage
        if hasattr(response, "content"):
            return {"messages": [AIMessage(content=response.content)]}
        # Last resort: convert to string
        return {"messages": [AIMessage(content=str(response))]}


if __name__ == "__main__":
    from langgraph_agent.llms.groq_llm import GroqLLM
    from langchain_core.messages import HumanMessage, SystemMessage

    # Create LLM instance
    user_controls_input = {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "selected_llm": "openai/gpt-oss-20b",
    }
    llm = GroqLLM(user_controls_input)
    llm = llm.get_base_llm()

    # Create RestaurantRecommendationNode instance with the LLM
    node = BasicChatbotNode(llm)

    # Example conversation history
    state = {
        "messages": [
            SystemMessage(content="You are a helpful and efficient assistant."),
            HumanMessage(content="Hi"),
        ]
    }

    # Call the search_node method and print the result
    result = node.process(state)
    print("Basic Chatbot Node Result:", result)
