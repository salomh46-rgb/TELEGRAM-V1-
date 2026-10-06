#!/usr/bin/env python3
"""
Entrypoint to run the Telegram v1 Async Relay Server.
"""

import asyncio
import logging
import sys
from telegram_v1.server.core import TelegramServer

# Configure clear logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


async def main():
    host = "127.0.0.1"
    port = 8443
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    server = TelegramServer(host=host, port=port)
    await server.start()

    try:
        # Keep running until Ctrl+C
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nTo'xtatilmoqda...")
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
