from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Notifier(ABC):
    @abstractmethod
    def notify_new_messages(self, count: int) -> None:
        pass
    @abstractmethod
    def deliver_summaries(self, summaries: List[Dict[str, Any]]) -> None:
        pass

class MockNotifier(Notifier):
    def notify_new_messages(self, count: int) -> None:
        print(f"[MockNotifier] {count} new email(s) received.")
    def deliver_summaries(self, summaries: List[Dict[str, Any]]) -> None:
        for summary in summaries:
            print(f"[MockNotifier] Summary for email {summary['id']}: {summary['summary']}")


class ConsoleNotifier(Notifier):
    """Console-based implementation for development/testing."""
    def notify_new_messages(self, count: int) -> None:
        print(f"{count} new email(s) received.")

    def deliver_summaries(self, summaries: List[Dict[str, Any]]) -> None:
        for summary in summaries:
            print(f"Summary for email {summary['id']}: {summary['summary']}")


class WhatsAppNotifier(Notifier):
    """WhatsApp-based implementation for production."""
    def __init__(self, api_key: str, phone_number: str):
        # Initialize WhatsApp API client (e.g., using Twilio)
        pass

    def notify_new_messages(self, count: int) -> None:
        # Send WhatsApp message: f"{count} new email(s) received."
        pass

    def deliver_summaries(self, summaries: List[Dict[str, Any]]) -> None:
        # Send WhatsApp messages with summaries
        pass