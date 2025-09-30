from typing import List, Dict, Any
from emailBroker.state_manager import StateManager


class EmailSummarizer:
    """
    Summarizes new emails using an injected LLM backend.
    """

    def __init__(self, llm_backend, state: StateManager):
        """
        :param llm_backend: An object with summarize(text: str) -> str
        :param state: StateManager instance
        """
        self.llm = llm_backend
        self.state = state

    def summarize_new_emails(self) -> List[Dict[str, Any]]:
        """
        Summarize all retrieved (not yet delivered) emails.
        Returns a list of {id, subject, summary}.
        Marks them as delivered after summarization.
        """
        retrieved = self.state.get_messages_by_status("retrieved")
        summaries = []

        for msg_id, msg in retrieved.items():
            subject = msg["subject"]
            body = msg["body"]

            summary = self.llm.summarize(body)

            # Persist summary + mark as delivered
            self.state.set_message_summary(msg_id, summary)
            self.state.mark_message_delivered(msg_id)

            summaries.append({
                "id": msg_id,
                "subject": subject,
                "summary": summary
            })

        return summaries
