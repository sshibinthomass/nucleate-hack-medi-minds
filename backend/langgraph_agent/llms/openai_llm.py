import os
from langchain_openai import ChatOpenAI
import dotenv

dotenv.load_dotenv()


class OpenAiLLM:
    def __init__(self, user_controls_input):
        self.user_controls_input = user_controls_input

    def get_base_llm(self):
        """Return the base ChatOpenAI LLM instance"""
        openai_api_key = self.user_controls_input.get("OPENAI_API_KEY", "")
        selected_openai_model = self.user_controls_input.get(
            "selected_llm", "gpt-4.1-mini"
        )
        return ChatOpenAI(api_key=openai_api_key, model=selected_openai_model)


if __name__ == "__main__":
    # Example user_controls_input
    user_controls_input = {
        "OPENAI_API_KEY": os.getenv(
            "OPENAI_API_KEY", ""
        ),  # Use env var or set your key here
        "selected_llm": "gpt-4.1-mini",  # Replace with a valid model for your OpenAI account
    }

    openai_llm = OpenAiLLM(user_controls_input)
    llm = openai_llm.get_base_llm()
    if llm:
        prompt = "What is the capital of Germany?"
        try:
            response = llm.invoke(prompt)
            print("Response:", response)
        except Exception as e:
            print("Error during invocation:", e)
    else:
        print("LLM could not be initialized.")
