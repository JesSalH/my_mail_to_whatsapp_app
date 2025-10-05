import json
import os
from typing import Dict, Any, Optional, List

STATE_FILE = os.path.join(os.path.dirname(__file__), "broker_state.json")


# emailBroker/state_manager.py
import os, json

class StateManager:
    def __init__(self, state_file: str = None):
        # ✅ Always use the same absolute path under emailBroker/
        if state_file is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            state_file = os.path.join(base_dir, "broker_state.json")
        self.state_file = state_file

        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        else:
            self.state = {"messages": {}, "last_history_id": None}
            self._save_state()

    def reload_state(self) -> None:
        """Reload the state from the JSON file to ensure it's up-to-date."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        else:
            self.state = {"messages": {}, "last_history_id": None}
            self._save_state()

    def _save_state(self):
        # ✅ Flush and fsync to be sure the data is written before Flask sends the event
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())


    def _load_state(self) -> None:
        """Load broker state from JSON file."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                try:
                    self.state = json.load(f)
                except json.JSONDecodeError:
                    self.state = {"last_history_id": None, "messages": {}}

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
            print("STATE -> set_message_summary -> setting summary for message id:", msg_id)
            self.state["messages"][msg_id]["summary"] = summary
            self._save_state()
        else:
            print("STATE -> set_message_summary -> message id not found in state:", msg_id)

    def mark_message_delivered(self, msg_id: str) -> None:
        """Mark a message as delivered (user has seen it)."""
        if msg_id in self.state["messages"]:
            status = self.state["messages"][msg_id]["status"]
            self.state["messages"][msg_id]["status"] = "delivered"
            print(f"STATE -> mark_message_delivered -> message id '{msg_id}' marked as: {status}")
            self._save_state()

    def get_messages_by_status(self, status: str) -> Dict[str, Any]:
        """Return all messages with a given status (retrieved/delivered), reloading state first."""
        self.reload_state()  # Refresh from file to get latest data
        return {
            mid: msg for mid, msg in self.state["messages"].items()
            if msg.get("status") == status
        }

    def get_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full record of a message by ID, reloading state first."""
        self.reload_state()  # Refresh from file to get latest data
        return self.state["messages"].get(msg_id)

    def reset_state(self) -> None:
        """Clear all stored state."""
        self.state = {"last_history_id": None, "messages": {}}
        self._save_state()
