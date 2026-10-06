"""
Interactive Terminal Client for Telegram v1.
Features ANSI styling, real-time message stream, and seamless E2E secret chat commands.
"""

import asyncio
import sys
from datetime import datetime
from telegram_v1.client.core import TelegramClient

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ANSI Color Codes
CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


BANNER = f"""
{BLUE}  _______   _                                         __     __  __ {RESET}
{BLUE} |__   __| | |                                        \\ \\   / / /_ |{RESET}
{CYAN}    | | ___| | ___  __ _ _ __ __ _ _ __ ___   __   __  \\ \\_/ /   | |{RESET}
{CYAN}    | |/ _ \\ |/ _ \\/ _` | '__/ _` | '_ ` _ \\  \\ \\ / /   \\   /    | |{RESET}
{BLUE}    | |  __/ |  __/ (_| | | | (_| | | | | | |  \\ V /     | |     | |{RESET}
{BLUE}    |_|\\___|_|\\___|\\__, |_|  \\__,_|_| |_| |_|   \\_/      |_|     |_|{RESET}
{CYAN}                    __/ |                                           {RESET}
{CYAN}                   |___/     {BOLD}MTProto 1.0 Real-Time Secure Engine{RESET}
{DIM}           Architecture: Nikolai & Pavel Durov (August 2013){RESET}
----------------------------------------------------------------------
"""


class TelegramCLI:
    def __init__(self, host: str = "127.0.0.1", port: int = 8443):
        self.client = TelegramClient(host=host, port=port)
        self.running = True

    def setup_callbacks(self):
        def on_msg(data: dict):
            sender = data.get("sender", "unknown")
            text = data.get("text", "")
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n{CYAN}[{now}] 💬 @{sender}:{RESET} {text}")
            print(f"{BOLD}> {RESET}", end="", flush=True)

        def on_group(data: dict):
            sender = data.get("sender", "unknown")
            group = data.get("group", "#general")
            text = data.get("text", "")
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n{BLUE}[{now}] 👥 [{group}] @{sender}:{RESET} {text}")
            print(f"{BOLD}> {RESET}", end="", flush=True)

        def on_secret(data: dict):
            sender = data.get("sender", "unknown")
            text = data.get("text", "")
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n{MAGENTA}{BOLD}[{now}] 🔒 [SECRET E2E] @{sender}:{RESET} {MAGENTA}{text}{RESET}")
            print(f"{BOLD}> {RESET}", end="", flush=True)

        def on_notify(text: str):
            print(f"\n{YELLOW}{text}{RESET}")
            print(f"{BOLD}> {RESET}", end="", flush=True)

        def on_users(users: list):
            print(f"\n{GREEN}--- 🌐 ONLAYN FOYDALANUVCHILAR ({len(users)}) ---{RESET}")
            for u in users:
                print(f"  • @{u['username']} ({u['display_name']}) - {GREEN}online{RESET}")
            print(f"{GREEN}------------------------------------------{RESET}")
            print(f"{BOLD}> {RESET}", end="", flush=True)

        self.client.on_message_callback = on_msg
        self.client.on_group_callback = on_group
        self.client.on_secret_callback = on_secret
        self.client.on_notification_callback = on_notify
        self.client.on_user_list_callback = on_users

    async def run(self):
        print(BANNER)
        print(f"{YELLOW}⏳ Telegram v1 serveriga ulanmoqda...{RESET}")
        try:
            await self.client.connect()
            print(f"{GREEN}✅ Bog'lanish o'rnatildi! Diffie-Hellman shifrlash kaliti: {self.client.auth_key_id.hex()[:16]}...{RESET}\n")
        except Exception as e:
            print(f"{RED}❌ Serverga ulanib bo'lmadi ({self.client.host}:{self.client.port}): {e}{RESET}")
            print(f"{DIM}Server ishga tushirilganligiga ishonch hosil qiling (python run_server.py){RESET}")
            return

        self.setup_callbacks()

        # Prompt for username and display name
        username = input(f"{BOLD}Telegram username kiriting (masalan: jasper): {RESET}").strip()
        if not username:
            username = "user_" + self.client.auth_key_id.hex()[:4]

        display_name = input(f"{BOLD}Ismingiz (Display name): {RESET}").strip()
        if not display_name:
            display_name = username

        await self.client.login(username, display_name)
        print(f"\n{GREEN}🚀 Xush kelibsiz, {display_name} (@{username})!{RESET}")
        self.print_help()

        # Input loop using run_in_executor
        loop = asyncio.get_running_loop()
        while self.running:
            try:
                line = await loop.run_in_executor(None, input, f"{BOLD}> {RESET}")
                line = line.strip()
                if not line:
                    continue

                if line.startswith("/"):
                    await self.handle_command(line)
                else:
                    # Default: send to public #general group
                    await self.client.send_group_message(line)
            except (KeyboardInterrupt, EOFError):
                break

        print(f"\n{YELLOW}Chiqilmoqda...{RESET}")
        await self.client.disconnect()

    async def handle_command(self, cmd_line: str):
        parts = cmd_line.split(" ", 2)
        cmd = parts[0].lower()

        if cmd in ("/exit", "/quit"):
            self.running = False

        elif cmd == "/help":
            self.print_help()

        elif cmd == "/users":
            await self.client.request_user_list()

        elif cmd == "/msg":
            if len(parts) < 3:
                print(f"{RED}Foydalanish: /msg <username> <xabar matni>{RESET}")
                return
            target = parts[1].lstrip("@")
            text = parts[2]
            await self.client.send_message(target, text)
            print(f"{DIM}📤 @{target} ga yuborildi: {text}{RESET}")

        elif cmd == "/secret":
            if len(parts) < 2:
                print(f"{RED}Foydalanish: /secret <username>{RESET}")
                return
            target = parts[1].lstrip("@")
            await self.client.start_secret_chat(target)

        elif cmd == "/smsg":
            if len(parts) < 3:
                print(f"{RED}Foydalanish: /smsg <username> <maxfiy matn>{RESET}")
                return
            target = parts[1].lstrip("@")
            text = parts[2]
            try:
                await self.client.send_secret_message(target, text)
                print(f"{MAGENTA}🔒 [SECRET E2E] @{target} ga yuborildi: {text}{RESET}")
            except Exception as e:
                print(f"{RED}Xatolik: {e}{RESET}")

        elif cmd == "/group":
            if len(parts) < 2:
                print(f"{RED}Foydalanish: /group <xabar matni>{RESET}")
                return
            text = cmd_line[7:].strip()
            await self.client.send_group_message(text)

        else:
            print(f"{RED}Noma'lum buyruq: {cmd}. /help yozing.{RESET}")

    def print_help(self):
        print(f"""
{CYAN}--- 📖 BUYRUQLAR RO'YXATI ---{RESET}
  {BOLD}/msg <username> <matn>{RESET}      - Shaxsiy to'g'ridan-to'g'ri xabar yuborish
  {BOLD}/secret <username>{RESET}           - E2E Maxfiy Chat (Diffie-Hellman) ochish
  {BOLD}/smsg <username> <matn>{RESET}     - Maxfiy Chatda E2E shifrlangan xabar yozish
  {BOLD}/users{RESET}                      - Onlayn foydalanuvchilar ro'yxati
  {BOLD}<matn>{RESET}                      - Umumiy #general guruhiga xabar yozish
  {BOLD}/help{RESET}                       - Yordam oynasi
  {BOLD}/quit{RESET}                       - Dasturdan chiqish
{CYAN}----------------------------{RESET}
""")
