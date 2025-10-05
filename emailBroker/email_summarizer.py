from typing import List, Dict, Any
from emailBroker.state_manager import StateManager


class EmailSummarizer:
    """
    Summarizes emails using an injected LLM backend.
    Can summarize all retrieved emails or a specific list of IDs.
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
        email_ids = list(retrieved.keys())
        return self.summarize_emails(email_ids)

    def summarize_emails(self, email_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Summarize specific emails by ID.
        Returns a list of {id, subject, summary}.
        Marks them as delivered after summarization.
        """
        print(f"DEBUG SUMMARIZER using state file: {self.state.state_file}")

        print("SUMMARIZER -> summarize_emails -> these are the email ids we got in the summarize_emails method:", email_ids)
        summaries: List[Dict[str, Any]] = []

        for msg_id in email_ids:
            print(f"DEBUG SUMMARIZER: looking up {msg_id}")
            print("SUMMARIZER -> summarize_emails -> processing email ID:", msg_id)
            msg = self.state.get_message(msg_id)
            print("SUMMARIZER -> summarize_emails -> fetched message:", msg)
            if not msg:
                print("SUMMARIZER -> summarize_emails -> message not found or invalid for message id:", msg_id)
                continue  # skip invalid or missing IDs

            subject = msg["subject"]
            body = msg["body"]

            # Summarize using LLM
            summary = self.llm.summarize(body)

            # Update state
            self.state.set_message_summary(msg_id, summary)
            self.state.mark_message_delivered(msg_id)

            summaries.append({
                "id": msg_id,
                "subject": subject,
                "summary": summary
            })

        return summaries
