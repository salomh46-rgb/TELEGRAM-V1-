#!/usr/bin/env python3
"""
Autonomous Multi-Client Simulation for Telegram v1.
Demonstrates:
1. Server startup
2. Diffie-Hellman handshake for Alice and Bob
3. Real-time 1-to-1 messaging
4. End-to-End Secret Chat initialization & zero-knowledge encrypted messaging
5. Group broadcasts (#general)
"""

import asyncio
import sys
from telegram_v1.server.core import TelegramServer
from telegram_v1.client.core import TelegramClient

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

GREEN = "\033[92m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


async def run_simulation():
    print(f"\n{BOLD}{CYAN}=== 🚀 TELEGRAM v1 AVTONOM SIMULYATSIYASI BOSHLANDI ==={RESET}\n")

    # 1. Start Server on port 8444
    server_port = 8444
    server = TelegramServer(host="127.0.0.1", port=server_port)
    await server.start()
    print(f"{GREEN}✓ Server muvaffaqiyatli ishga tushirildi (Port: {server_port}){RESET}")

    # Events to signal message arrivals
    alice_received_secret = asyncio.Event()
    bob_received_secret = asyncio.Event()
    bob_received_direct = asyncio.Event()

    # 2. Setup Alice
    alice = TelegramClient(host="127.0.0.1", port=server_port)
    await alice.connect()
    await alice.login("alice", "Alisa Karimova")
    print(f"{GREEN}✓ Alice serverga ulandi va DH handshake qildi (AuthKey: {alice.auth_key_id.hex()[:12]}...){RESET}")

    # 3. Setup Bob
    bob = TelegramClient(host="127.0.0.1", port=server_port)
    await bob.connect()
    await bob.login("bob", "Bobur Mirzo")
    print(f"{GREEN}✓ Bob serverga ulandi va DH handshake qildi (AuthKey: {bob.auth_key_id.hex()[:12]}...){RESET}")

    # Set callbacks
    def bob_on_msg(data):
        print(f"  {CYAN}📩 Bob xabar oldi: '{data['text']}' (Yuboruvchi: @{data['sender']}){RESET}")
        bob_received_direct.set()

    def bob_on_secret(data):
        print(f"  {MAGENTA}🔒 [Bob E2E Secret Chat]: '{data['text']}' (Yuboruvchi: @{data['sender']}){RESET}")
        bob_received_secret.set()

    def alice_on_secret(data):
        print(f"  {MAGENTA}🔒 [Alice E2E Secret Chat]: '{data['text']}' (Yuboruvchi: @{data['sender']}){RESET}")
        alice_received_secret.set()

    bob.on_message_callback = bob_on_msg
    bob.on_secret_callback = bob_on_secret
    alice.on_secret_callback = alice_on_secret

    await asyncio.sleep(0.5)

    # 4. Direct Messaging Test
    print(f"\n{YELLOW}[1-BOSQICH] 1-to-1 To'g'ridan-to'g'ri xabar jo'natish:{RESET}")
    print("  Alice -> Bob: 'Salom Bobur! Telegram v1 arxitekturasi ishga tushdi.'")
    await alice.send_message("bob", "Salom Bobur! Telegram v1 arxitekturasi ishga tushdi.")
    await asyncio.wait_for(bob_received_direct.wait(), timeout=3.0)

    # 5. E2E Secret Chat Test
    print(f"\n{YELLOW}[2-BOSQICH] E2E Secret Chat (Mijozlararo alohida Diffie-Hellman):{RESET}")
    print("  Alice Bobur bilan E2E Maxfiy Chat so'rovini boshlamoqda...")
    await alice.start_secret_chat("bob")
    
    # Wait for DH exchange between Alice and Bob to finalize
    await asyncio.sleep(1.0)

    print("  Alice -> Bob (E2E Shifrlangan): 'Maxfiy xabar: Server buni o'qiy olmaydi!'")
    await alice.send_secret_message("bob", "Maxfiy xabar: Server buni o'qiy olmaydi!")
    await asyncio.wait_for(bob_received_secret.wait(), timeout=3.0)

    # Bob replies to Alice in secret chat
    print("  Bob -> Alice (E2E Shifrlangan): 'Qabul qildim Alisa, to'liq shifrlangan!'")
    await bob.send_secret_message("alice", "Qabul qildim Alisa, to'liq shifrlangan!")
    await asyncio.wait_for(alice_received_secret.wait(), timeout=3.0)

    # 6. Group Messaging Test
    print(f"\n{YELLOW}[3-BOSQICH] #general guruhiga xabar:{RESET}")
    await alice.send_group_message("Barchaga salom! Bu umumiy kanal.")
    await asyncio.sleep(0.5)

    print(f"\n{BOLD}{GREEN}=== 🎯 BARCHA BOSQICHLAR 100% MUVAFFAQIYATLI O'TDI! ==={RESET}\n")

    # Clean up
    await alice.disconnect()
    await bob.disconnect()
    await server.stop()


if __name__ == "__main__":
    asyncio.run(run_simulation())
