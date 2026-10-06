"""
End-to-end integration tests for Telegram v1 Server & Client.
"""

import asyncio
import pytest
from telegram_v1.server.core import TelegramServer
from telegram_v1.client.core import TelegramClient


@pytest.mark.asyncio
async def test_full_client_server_lifecycle():
    port = 8499
    server = TelegramServer(host="127.0.0.1", port=port)
    await server.start()

    received_event = asyncio.Event()
    received_message = {}

    try:
        # Client 1: Alice
        alice = TelegramClient(host="127.0.0.1", port=port)
        await alice.connect()
        await alice.login("alice", "Alisa")

        # Client 2: Bob
        bob = TelegramClient(host="127.0.0.1", port=port)
        await bob.connect()
        await bob.login("bob", "Bobur")

        def on_bob_msg(data):
            received_message.update(data)
            received_event.set()

        bob.on_message_callback = on_bob_msg

        # Alice sends message to Bob
        await asyncio.sleep(0.2)
        await alice.send_message("bob", "Salom Bobur!")

        # Wait for delivery
        await asyncio.wait_for(received_event.wait(), timeout=3.0)

        assert received_message["sender"] == "alice"
        assert received_message["text"] == "Salom Bobur!"

        await alice.disconnect()
        await bob.disconnect()
    finally:
        await server.stop()
