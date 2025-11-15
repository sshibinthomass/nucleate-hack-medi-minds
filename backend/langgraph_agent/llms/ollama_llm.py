from langchain_ollama import ChatOllama
import dotenv

dotenv.load_dotenv()


class OllamaLLM:
    def __init__(self, user_controls_input):
        self.user_controls_input = user_controls_input

    def get_base_llm(self):
        """Return the base Ollama LLM instance"""
        selected_ollama_model = self.user_controls_input["selected_llm"]
        ollama_base_url = self.user_controls_input.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        return ChatOllama(model=selected_ollama_model, base_url=ollama_base_url)   


if __name__ == "__main__":
    # Example usage
    user_controls_input = {
        "selected_llm": "gemma3:1b",
        "OLLAMA_BASE_URL": "http://localhost:11434",
    }

    ollama_llm = OllamaLLM(user_controls_input)
    llm = ollama_llm.get_base_llm()

    # Simple test prompt
    prompt = "Hello, who won the FIFA World Cup in 2018?"
    try:
        # For Ollama, you typically use .invoke() or .predict()
        response = llm.invoke(prompt)
        print(response)
    except Exception as e:
        print("Error during LLM invocation:", e)
        print("Make sure Ollama is running and the model is available.")
