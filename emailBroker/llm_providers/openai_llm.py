import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

class OpenAILLM:
    """
    OpenAI-based LLM provider.
    Reads API key from .env (OPENAI_API_KEY).
    Provides summarize() and chat() methods.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY not found in .env file")

        # Create OpenAI client
        self.client = OpenAI(api_key=api_key)
        self.model = model

        # Console feedback
        print("✅ OpenAILLM initialized successfully")
        print(f"   Using model: {self.model}")

    def summarize(self, text: str) -> str:
        """
        Summarize the given text into a short digest.
        """
        prompt = f"Summarize the following email in 2-3 sentences:\n\n{text}"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an assistant that summarizes emails concisely."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()

    def chat(self, prompt: str) -> str:
        """
        General chat interface for freeform user queries.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions about emails."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
