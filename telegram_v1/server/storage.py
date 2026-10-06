"""
Storage layer for Telegram v1 server.
Handles persistent/in-memory message queues, offline inboxes, and user state.
"""

from typing import Dict, List, Optional
import time


class MessageStorage:
    """
    Manages offline delivery queues, chat history, and group memberships.
    """

    def __init__(self):
        # username -> list of undelivered message payloads
        self._offline_inbox: Dict[str, List[dict]] = {}
        # group_name -> set of username members
        self._groups: Dict[str, set] = {"#general": set()}
        # username -> user metadata
        self._registered_users: Dict[str, dict] = {}

    def register_user(self, username: str, display_name: str) -> dict:
        user = {
            "username": username,
            "display_name": display_name,
            "created_at": time.time(),
        }
        self._registered_users[username] = user
        if username not in self._offline_inbox:
            self._offline_inbox[username] = []
        # Auto join #general group
        self._groups["#general"].add(username)
        return user

    def get_user(self, username: str) -> Optional[dict]:
        return self._registered_users.get(username)

    def queue_offline_message(self, recipient: str, message_data: dict) -> None:
        """Stores a message until recipient comes back online."""
        if recipient not in self._offline_inbox:
            self._offline_inbox[recipient] = []
        self._offline_inbox[recipient].append(message_data)

    def retrieve_and_clear_offline_messages(self, username: str) -> List[dict]:
        """Fetches pending messages for user upon reconnection and clears queue."""
        messages = self._offline_inbox.get(username, [])
        self._offline_inbox[username] = []
        return messages

    def get_group_members(self, group_name: str) -> set:
        return self._groups.get(group_name, set())

    def join_group(self, username: str, group_name: str) -> None:
        if group_name not in self._groups:
            self._groups[group_name] = set()
        self._groups[group_name].add(username)
