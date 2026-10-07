#!/usr/bin/env python3
"""
Telegram v2 Unified Server:
Runs both the MTProto 1.0 TCP relay engine and the modern FastAPI Web PWA & WebSocket Gateway.
"""

import asyncio
import logging
import sys
import uvicorn

from telegram_v1.server.core import TelegramServer
from telegram_v1.web.portal import create_web_portal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


async def main():
    tcp_port = 8443
    web_port = 8080
    if len(sys.argv) > 1:
        web_port = int(sys.argv[1])

    # 1. Start MTProto TCP Core
    tcp_server = TelegramServer(host="127.0.0.1", port=tcp_port)
    await tcp_server.start()

    # 2. Start Web Portal & WebSocket Gateway
    app = create_web_portal(tcp_server)
    config = uvicorn.Config(app=app, host="127.0.0.1", port=web_port, log_level="warning")
    uv_server = uvicorn.Server(config)

    print("\n" + "=" * 65)
    print("⚡ TELEGRAM v2 (Independent Core & Anti-Censorship)")
    print(f"📡 MTProto TCP Server:        tcp://127.0.0.1:{tcp_port}")
    print(f"🌐 Web PWA & Chat Client:     http://127.0.0.1:{web_port}")
    print(f"🔍 SEO Channel Showcase:     http://127.0.0.1:{web_port}/channel/general")
    print(f"🛡️  Upstash Anti-Spam Guard:  {'🟢 Faol (Cloud Redis)' if tcp_server.rate_limiter.is_redis_configured else '🟡 Lokal In-Memory'}")
    print(f"📧 Resend Offline Notifier:  {'🟢 Faol (Resend API)' if tcp_server.notifier.is_configured else '⚪ Standby'}")
    print("=" * 65 + "\n")

    try:
        await uv_server.serve()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nTo'xtatilmoqda...")
    finally:
        await tcp_server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
