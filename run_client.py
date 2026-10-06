#!/usr/bin/env python3
"""
Entrypoint to run the Telegram v1 Interactive CLI Terminal.
"""

import asyncio
import sys
from telegram_v1.client.cli import TelegramCLI


async def main():
    host = "127.0.0.1"
    port = 8443
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    cli = TelegramCLI(host=host, port=port)
    await cli.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDastur to'xtatildi.")
