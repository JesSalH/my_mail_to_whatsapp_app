from typing import Callable, List, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NewEmailsArrivedEvent:
    """Event triggered when new emails are received and stored."""
    email_ids: List[str]
    timestamp: datetime

class EventBus:
    """Central event bus for publishing and subscribing to events."""
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    def subscribe(self, event_name: str, callback: Callable) -> None:
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)
    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        if event_name in self._subscribers:
            self._subscribers[event_name].remove(callback)
    def publish(self, event_name: str, event_data: any) -> None:
        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                callback(event_data)

event_bus = EventBus()
NEW_EMAILS_ARRIVED = "new_emails_arrived"