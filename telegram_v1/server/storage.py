"""
Storage layer for Telegram v1/v2 server.
Handles persistent/in-memory message queues, offline inboxes, user profiles with email,
and public channels for SEO showcase & web streaming.
"""

import time
from typing import Dict, List, Optional, Set


class MessageStorage:
    """
    Manages offline delivery queues, chat history, public channels, and group memberships.
    """

    def __init__(self):
        # username -> list of undelivered message payloads
        self._offline_inbox: Dict[str, List[dict]] = {}
        # group_name -> set of username members
        self._groups: Dict[str, Set[str]] = {
            "#general": set(),
            "#announcements": set(),
            "#crypto_news": set(),
        }
        # channel_name -> list of public posts
        self._channel_posts: Dict[str, List[dict]] = {
            "#general": [],
            "#announcements": [
                {
                    "id": "post-1",
                    "sender": "admin",
                    "text": "⚡ Telegram v2 (Independent Core) ishga tushirildi! Web PWA, E2E shifrlash va SEO vitrina faol.",
                    "timestamp": time.time() - 3600,
                    "views": 1420,
                },
                {
                    "id": "post-2",
                    "sender": "admin",
                    "text": "🛡️ Upstash Redis Anti-Spam va Resend Multi-Channel zaxira bildirishnomalari ulandi.",
                    "timestamp": time.time() - 1800,
                    "views": 890,
                },
            ],
            "#crypto_news": [
                {
                    "id": "post-3",
                    "sender": "jasper",
                    "text": "🚀 Decentralized Messaging & Direct Payments shlyuzi muvaffaqiyatli sinovdan o'tkazildi.",
                    "timestamp": time.time() - 900,
                    "views": 530,
                }
            ],
        }
        # username -> user metadata (display_name, email, created_at)
        self._registered_users: Dict[str, dict] = {}

    def register_user(
        self,
        username: str,
        display_name: str,
        email: Optional[str] = None,
    ) -> dict:
        username = username.strip().lower()
        user = {
            "username": username,
            "display_name": display_name or username,
            "email": email.strip() if email else None,
            "created_at": time.time(),
        }
        self._registered_users[username] = user
        if username not in self._offline_inbox:
            self._offline_inbox[username] = []
        
        # Auto-join default groups
        self._groups["#general"].add(username)
        self._groups["#announcements"].add(username)
        return user

    def get_user(self, username: str) -> Optional[dict]:
        return self._registered_users.get(username.strip().lower())

    def get_user_email(self, username: str) -> Optional[str]:
        user = self.get_user(username)
        return user.get("email") if user else None

    def queue_offline_message(self, recipient: str, message_data: dict) -> None:
        """Stores a message until recipient comes back online."""
        recipient = recipient.strip().lower()
        if recipient not in self._offline_inbox:
            self._offline_inbox[recipient] = []
        self._offline_inbox[recipient].append(message_data)

    def retrieve_and_clear_offline_messages(self, username: str) -> List[dict]:
        """Fetches pending messages for user upon reconnection and clears queue."""
        username = username.strip().lower()
        messages = self._offline_inbox.get(username, [])
        self._offline_inbox[username] = []
        return messages

    def get_group_members(self, group_name: str) -> Set[str]:
        return self._groups.get(group_name, set())

    def join_group(self, username: str, group_name: str) -> None:
        if group_name not in self._groups:
            self._groups[group_name] = set()
        self._groups[group_name].add(username.strip().lower())

    def post_to_channel(self, channel_name: str, sender: str, text: str) -> dict:
        """Publishes a post to a public channel."""
        if not channel_name.startswith("#"):
            channel_name = f"#{channel_name}"
        if channel_name not in self._channel_posts:
            self._channel_posts[channel_name] = []

        post = {
            "id": f"post-{len(self._channel_posts[channel_name]) + 1}",
            "sender": sender,
            "text": text,
            "timestamp": time.time(),
            "views": 1,
        }
        self._channel_posts[channel_name].append(post)
        return post

    def get_channel_messages(self, channel_name: str, limit: int = 50) -> List[dict]:
        """Retrieves messages for a public channel (used for SEO vitrina & web viewer)."""
        if not channel_name.startswith("#"):
            channel_name = f"#{channel_name}"
        posts = self._channel_posts.get(channel_name, [])
        return posts[-limit:]

    def get_public_channels(self) -> List[dict]:
        """Returns list of public channels with metadata for web portal navigation."""
        result = []
        for ch_name, posts in self._channel_posts.items():
            result.append({
                "slug": ch_name.lstrip("#"),
                "name": ch_name,
                "posts_count": len(posts),
                "subscribers_count": len(self._groups.get(ch_name, set())),
                "last_post": posts[-1] if posts else None,
            })
        return result
