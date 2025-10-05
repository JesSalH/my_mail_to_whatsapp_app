from typing import Callable, List, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NewEmailsArrivedEvent:
    """Event triggered when new emails are received and stored."""
    email_ids: List[str]
    timestamp: datetime