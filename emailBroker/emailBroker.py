# emailBroker/emailBroker.py
from typing import Dict, Any, Optional, List
from emailBroker.state_manager import StateManager
from emailBroker.email_summarizer import EmailSummarizer
from emailBroker.notifications import Notifier

class EmailBroker:
    """
    Orchestrates between state, summarizer, and notifier.
    Flow:
      - notify_new_messages(): called after Gmail push → tells user "X new emails".
      - deliver_new_summaries(): on user request → summarize and deliver new messages.
      - show_full_message(id): return subject + body for a given email.
    """
    def __init__(self, state: StateManager, summarizer: EmailSummarizer, notifier: Notifier):
        self.state = state
        self.summarizer = summarizer
        self.notifier = notifier

    def notify_new_messages(self, email_ids: Optional[List[str]] = None) -> None:
        """Called after Gmail push → notify user of count only, using provided email_ids or all retrieved."""
        if email_ids is not None:
            count = len(email_ids)
        else:
            retrieved = self.state.get_messages_by_status("retrieved")
            count = len(retrieved)
        self.notifier.notify_new_messages(count)

    def deliver_new_summaries(self, email_ids: Optional[List[str]] = None) -> None:
        """On user request → summarize and deliver new messages, using provided email_ids or all new emails."""
        if email_ids is not None:
            summaries = self.summarizer.summarize_emails(email_ids)  # Use specific IDs method
        else:
            summaries = self.summarizer.summarize_new_emails()  # Fallback to all new
        self.notifier.deliver_summaries(summaries)

    def show_full_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Return full email by ID (subject + body)."""
        return self.state.get_message(msg_id)