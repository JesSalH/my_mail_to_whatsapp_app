import json
import os
from typing import Dict, Any, Optional, List

STATE_FILE = os.path.join(os.path.dirname(__file__), "broker_state.json")


class StateManager:
    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        self.state: Dict[str, Any] = {
            "last_history_id": None,
            "messages": {}
        }
        self._load_state()

    def _load_state(self) -> None:
        """Load broker state from JSON file."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                try:
                    self.state = json.load(f)
                except json.JSONDecodeError:
                    self.state = {"last_history_id": None, "messages": {}}

    def _save_state(self) -> None:
        """Persist state to disk."""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    # ------------------------------
    # History ID handling
    # ------------------------------
    def get_last_history_id(self) -> Optional[str]:
        return self.state.get("last_history_id")

    def set_last_history_id(self, history_id: str) -> None:
        self.state["last_history_id"] = history_id
        self._save_state()

    # ------------------------------
    # Message handling
    # ------------------------------
    def add_retrieved_message(self, msg_id: str, subject: str, body: str) -> None:
        """Store a newly retrieved message (raw, not yet summarized)."""
        if msg_id not in self.state["messages"]:
            self.state["messages"][msg_id] = {
                "status": "retrieved",
                "subject": subject,
                "summary": None,
                "body": body
            }
            self._save_state()

    def set_message_summary(self, msg_id: str, summary: str) -> None:
        """Attach LLM summary to a retrieved message."""
        if msg_id in self.state["messages"]:
            self.state["messages"][msg_id]["summary"] = summary
            self._save_state()

    def mark_message_delivered(self, msg_id: str) -> None:
        """Mark a message as delivered (user has seen it)."""
        if msg_id in self.state["messages"]:
            self.state["messages"][msg_id]["status"] = "delivered"
            self._save_state()

    def get_messages_by_status(self, status: str) -> Dict[str, Any]:
        """Return all messages with a given status (retrieved/delivered)."""
        return {
            mid: msg for mid, msg in self.state["messages"].items()
            if msg.get("status") == status
        }

    def get_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full record of a message by ID."""
        return self.state["messages"].get(msg_id)

    def reset_state(self) -> None:
        """Clear all stored state."""
        self.state = {"last_history_id": None, "messages": {}}
        self._save_state()
