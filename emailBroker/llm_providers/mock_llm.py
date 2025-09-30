class MockLLM:
    """
    A mock LLM provider for testing the email summarizer and broker.
    Does not call any real API.
    """

    def summarize(self, text: str) -> str:
        """
        Fake summarization: return the first 60 characters as a "summary".
        """
        preview = text[:60].replace("\n", " ")
        return f"(Summary) {preview}..."

    def chat(self, prompt: str) -> str:
        """
        Fake chat: just echo the user input.
        """
        return f"(LLM echo) You said: {prompt}"
