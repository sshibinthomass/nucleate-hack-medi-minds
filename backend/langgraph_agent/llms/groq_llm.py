import os
from langchain_groq import ChatGroq
import dotenv
dotenv.load_dotenv()

class GroqLLM:
    def __init__(self, user_contols_input):
        self.user_controls_input = user_contols_input

    def get_base_llm(self):
        """Return the base ChatGroq LLM instance"""
        groq_api_key = self.user_controls_input["GROQ_API_KEY"]
        selected_groq_model = self.user_controls_input["selected_llm"]
        return ChatGroq(api_key=groq_api_key, model=selected_groq_model)

if __name__ == "__main__":
    # Example usage
    user_controls_input = {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
        "selected_llm": "openai/gpt-oss-20b"
    }

    groq_llm = GroqLLM(user_controls_input)
    
    llm = groq_llm.get_base_llm()

    prompt = "Hello, who won the FIFA World Cup in 2018?"
    response = llm.invoke(prompt)
    print(response)
