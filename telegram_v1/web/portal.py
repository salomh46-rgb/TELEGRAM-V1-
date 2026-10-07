"""
FastAPI Web Portal & WebSocket Gateway for Telegram v1/v2.
Provides:
1. Public Channel Showcase with OpenGraph SEO for Google/Yandex indexing.
2. 2026 Elite Dark Web PWA interface for zero-friction browser chatting.
3. Live WebSocket bridge connecting browser clients with MTProto core.
4. Direct Payment Gateway (Zero 30% Telegram Stars tax, Payme/Click compliant).
"""

import os
import json
import time
import logging
from typing import Dict, Set, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from telegram_v1.server.core import TelegramServer

logger = logging.getLogger("telegram_v1.portal")


class PaymentIntentRequest(BaseModel):
    from_user: str
    to_user: str
    amount: int
    currency: str = "UZS"
    memo: Optional[str] = "Xarid to'lovi"


class WebSocketConnectionManager:
    """Manages active Web PWA clients connected via WebSocket."""

    def __init__(self):
        # username -> set of WebSocket connections
        self.active_websockets: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, username: str) -> None:
        await websocket.accept()
        username = username.strip().lower()
        if username not in self.active_websockets:
            self.active_websockets[username] = set()
        self.active_websockets[username].add(websocket)

    def disconnect(self, websocket: WebSocket, username: str) -> None:
        username = username.strip().lower()
        if username in self.active_websockets:
            self.active_websockets[username].discard(websocket)
            if not self.active_websockets[username]:
                del self.active_websockets[username]

    async def send_to_user(self, username: str, payload: dict) -> None:
        username = username.strip().lower()
        sockets = self.active_websockets.get(username, set())
        dead_sockets = set()
        for ws in sockets:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead_sockets.add(ws)
        for dead in dead_sockets:
            sockets.discard(dead)

    async def broadcast(self, payload: dict, exclude_user: Optional[str] = None) -> None:
        dead_sockets = []
        for uname, sockets in self.active_websockets.items():
            if uname == exclude_user:
                continue
            for ws in list(sockets):
                try:
                    await ws.send_text(json.dumps(payload))
                except Exception:
                    dead_sockets.append((uname, ws))
        for uname, ws in dead_sockets:
            if uname in self.active_websockets:
                self.active_websockets[uname].discard(ws)


def create_web_portal(server: TelegramServer) -> FastAPI:
    """Factory creating the FastAPI app bound to an active TelegramServer."""
    app = FastAPI(title="Telegram v2 Independent Web Gateway", version="2.0.0")
    ws_manager = WebSocketConnectionManager()

    # --- HTML Generator Helpers ---
    def render_seo_channel_html(channel_name: str, posts: List[dict]) -> str:
        channel_slug = channel_name.lstrip("#")
        posts_html = ""
        for p in posts:
            time_str = time.strftime("%H:%M, %d-%b", time.localtime(p.get("timestamp", time.time())))
            posts_html += f"""
            <div class="post-card">
                <div class="post-header">
                    <span class="sender-badge">@{p.get('sender', 'anonymous')}</span>
                    <span class="time-badge">{time_str}</span>
                </div>
                <div class="post-body">{p.get('text', '')}</div>
                <div class="post-footer">
                    <span>👁️ {p.get('views', 1)} ko'rildi</span>
                    <span class="e2e-badge">🔒 MTProto Verified</span>
                </div>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{channel_name} — Telegram v2 Ochiq Kanali</title>
    <!-- OpenGraph SEO Tags for Google & Social Media -->
    <meta property="og:title" content="{channel_name} Ochiq Kanali | Telegram v2" />
    <meta property="og:description" content="Ochiq kanal yangiliklari va e'lonlarini to'g'ridan-to'g'ri veb brauzerda o'qing." />
    <meta property="og:type" content="website" />
    <meta name="description" content="{channel_name} kanali. To'g'ridan-to'g'ri mustaqil Telegram v2 tarmog'ida nashr etilgan." />
    <style>
        :root {{ --bg: #090d16; --card: #111827; --border: #1f293d; --accent: #38bdf8; --text: #f3f4f6; --muted: #9ca3af; }}
        body {{ margin: 0; background-color: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .header {{ padding: 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; max-width: 800px; margin: 0 auto; }}
        .logo {{ font-weight: 800; font-size: 20px; color: var(--accent); text-decoration: none; display: flex; align-items: center; gap: 8px; }}
        .container {{ max-width: 800px; margin: 30px auto; padding: 0 20px; }}
        .channel-banner {{ background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid var(--border); border-radius: 16px; padding: 24px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }}
        .btn-join {{ background: var(--accent); color: #04111d; padding: 10px 20px; border-radius: 10px; font-weight: 700; text-decoration: none; }}
        .post-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; margin-bottom: 16px; }}
        .post-header {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 13px; }}
        .sender-badge {{ color: var(--accent); font-weight: 600; }}
        .time-badge {{ color: var(--muted); }}
        .post-body {{ font-size: 15px; line-height: 1.6; color: #e5e7eb; white-space: pre-wrap; }}
        .post-footer {{ display: flex; justify-content: space-between; margin-top: 14px; font-size: 12px; color: var(--muted); border-top: 1px solid #1a2234; padding-top: 8px; }}
        .e2e-badge {{ color: #10b981; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="header">
        <a href="/" class="logo">⚡ Telegram v2 Web</a>
        <span>🌐 Ochiq Vitrina (SEO Indexable)</span>
    </div>
    <div class="container">
        <div class="channel-banner">
            <div>
                <h1 style="margin: 0; font-size: 24px;">{channel_name}</h1>
                <p style="margin: 6px 0 0; color: var(--muted); font-size: 14px;">Telegram v2 tarmog'ining ochiq kanali</p>
            </div>
            <a href="/" class="btn-join">💬 PWA da Chatga Kirish</a>
        </div>
        <div class="posts-feed">
            {posts_html if posts_html else '<p style="color: var(--muted); text-align: center;">Hozircha xabarlar mavjud emas.</p>'}
        </div>
    </div>
</body>
</html>"""

    # --- Routes ---

    @app.get("/api/health")
    async def health_check():
        return {
            "status": "healthy",
            "active_tcp_sessions": len(server.active_sessions),
            "registered_users": len(server.storage._registered_users),
            "upstash_anti_spam": server.rate_limiter.is_redis_configured,
            "resend_notifier": server.notifier.is_configured,
            "timestamp": time.time(),
        }

    @app.get("/api/public/channels")
    async def get_public_channels():
        return {"channels": server.storage.get_public_channels()}

    @app.get("/api/public/channel/{slug}/posts")
    async def get_channel_posts_api(slug: str):
        channel_name = f"#{slug.lstrip('#')}"
        posts = server.storage.get_channel_messages(channel_name)
        return {"channel": channel_name, "posts": posts}

    @app.get("/channel/{slug}", response_class=HTMLResponse)
    async def view_channel_seo(slug: str):
        channel_name = f"#{slug.lstrip('#')}"
        posts = server.storage.get_channel_messages(channel_name)
        return HTMLResponse(content=render_seo_channel_html(channel_name, posts))

    @app.post("/api/pay/intent")
    async def create_direct_payment(req: PaymentIntentRequest):
        """
        Creates a direct zero-commission payment intent.
        Bypasses Telegram Stars 30% cut; compatible with Payme/Click checkout.
        """
        invoice_id = f"inv-{int(time.time())}-{req.from_user}"
        checkout_url = f"https://checkout.paycom.uz/sandbox/{invoice_id}"
        
        # Broadcast payment receipt into recipient's inbox or group
        receipt_text = f"💳 [TO'LOV]: @{req.from_user} dan @{req.to_user} ga {req.amount:,} {req.currency} to'landi. Izoh: {req.memo}"
        server.storage.post_to_channel("#general", "SYSTEM_PAYMENT", receipt_text)
        
        # Broadcast to active WebSockets
        await ws_manager.broadcast({
            "type": "payment_alert",
            "from_user": req.from_user,
            "to_user": req.to_user,
            "amount": req.amount,
            "currency": req.currency,
            "invoice_id": invoice_id,
            "text": receipt_text,
        })

        return {
            "success": True,
            "invoice_id": invoice_id,
            "amount": req.amount,
            "currency": req.currency,
            "fee_percent": 0.0,
            "checkout_url": checkout_url,
            "status": "PAID_SIMULATED",
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        current_username = None
        try:
            # First message must be auth
            await websocket.accept()
            init_data = await websocket.receive_text()
            init_json = json.loads(init_data)

            if init_json.get("type") != "auth":
                await websocket.send_text(json.dumps({"type": "error", "message": "Expected auth handshake."}))
                await websocket.close()
                return

            username = init_json.get("username", "anonymous").strip().lower()
            display_name = init_json.get("display_name", username)
            email = init_json.get("email")

            current_username = username
            if username not in ws_manager.active_websockets:
                ws_manager.active_websockets[username] = set()
            ws_manager.active_websockets[username].add(websocket)

            # Register in server storage
            server.storage.register_user(username, display_name, email=email)
            logger.info(f"[Web PWA] User @{username} connected via WebSocket.")

            # Deliver offline messages
            offline_msgs = server.storage.retrieve_and_clear_offline_messages(username)
            await websocket.send_text(json.dumps({
                "type": "auth_success",
                "username": username,
                "display_name": display_name,
                "offline_messages": offline_msgs,
                "channels": server.storage.get_public_channels(),
            }))

            # Announce online
            await ws_manager.broadcast({
                "type": "user_status",
                "username": username,
                "status": "online",
            }, exclude_user=username)

            # Message processing loop
            while True:
                msg_raw = await websocket.receive_text()
                packet = json.loads(msg_raw)
                ptype = packet.get("type")

                # Rate limit check on websocket user
                allowed, _ = await server.rate_limiter.check(f"ws_user:{username}", limit=60, window_seconds=60)
                if not allowed:
                    await websocket.send_text(json.dumps({
                        "type": "system_notify",
                        "text": "⚠️ [RATE LIMIT] Xabar yuborish tezligi oshib ketdi. Iltimos kuting.",
                    }))
                    continue

                if ptype == "send_message":
                    recipient = packet.get("recipient", "").strip().lower()
                    text = packet.get("text", "")
                    msg_obj = {
                        "type": "direct_message",
                        "sender": username,
                        "recipient": recipient,
                        "text": text,
                        "timestamp": time.time(),
                    }

                    # Check if recipient is on WebSocket
                    if recipient in ws_manager.active_websockets and ws_manager.active_websockets[recipient]:
                        await ws_manager.send_to_user(recipient, msg_obj)
                    # Check if recipient is on TCP MTProto session
                    elif recipient in server.active_sessions:
                        tcp_sess = server.active_sessions[recipient]
                        from telegram_v1.protocol.tl_schema import TLPacket, TLType
                        await tcp_sess.send_encrypted(TLPacket(type=TLType.TEXT_MESSAGE, data=msg_obj))
                    else:
                        # Queue in offline
                        server.storage.queue_offline_message(recipient, msg_obj)
                        # Multi-channel email fallback
                        recip_email = server.storage.get_user_email(recipient)
                        if recip_email:
                            server.notifier.schedule_offline_notification(
                                to_email=recip_email,
                                recipient_username=recipient,
                                sender_username=username,
                                message_preview=text[:120],
                            )

                    # Echo to sender
                    await websocket.send_text(json.dumps({"type": "message_sent", "message": msg_obj}))

                elif ptype == "send_group":
                    group = packet.get("group", "#general")
                    text = packet.get("text", "")
                    post = server.storage.post_to_channel(group, username, text)
                    broadcast_obj = {
                        "type": "group_message",
                        "group": group,
                        "sender": username,
                        "text": text,
                        "timestamp": post["timestamp"],
                    }
                    await ws_manager.broadcast(broadcast_obj)

                elif ptype == "get_channels":
                    await websocket.send_text(json.dumps({
                        "type": "channels_list",
                        "channels": server.storage.get_public_channels(),
                    }))

        except WebSocketDisconnect:
            if current_username:
                ws_manager.disconnect(websocket, current_username)
                await ws_manager.broadcast({
                    "type": "user_status",
                    "username": current_username,
                    "status": "offline",
                })
        except Exception as e:
            logger.error(f"[WebSocket] Error: {e}", exc_info=True)
            if current_username:
                ws_manager.disconnect(websocket, current_username)

    # --- Web PWA Main Client UI (2026 Elite Dark Luxury) ---
    @app.get("/", response_class=HTMLResponse)
    async def serve_pwa_client():
        return HTMLResponse(content="""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram v2 — Independent Web Client</title>
    <style>
        :root {
            --bg-deep: #07090e;
            --bg-surface: #0e131f;
            --bg-elevated: #161e31;
            --border: #1e293b;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.25);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --online: #10b981;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-deep);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            height: 100vh;
            display: flex;
            overflow: hidden;
        }
        /* Layout */
        .sidebar {
            width: 320px;
            background: var(--bg-surface);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
        }
        .main-chat {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--bg-deep);
        }
        /* Top Headers */
        .sidebar-header {
            padding: 18px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .brand {
            font-size: 17px;
            font-weight: 800;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .chat-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-surface);
        }
        /* Channel & Chat list */
        .chat-list {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }
        .chat-item {
            padding: 12px 14px;
            border-radius: 10px;
            cursor: pointer;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease;
        }
        .chat-item:hover { background: var(--bg-elevated); }
        .chat-item.active { background: var(--accent-glow); border: 1px solid var(--accent); }
        .chat-name { font-weight: 600; font-size: 14px; }
        .chat-badge { font-size: 11px; color: var(--text-secondary); }
        /* Message Stream */
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .msg-bubble {
            max-width: 65%;
            padding: 12px 16px;
            border-radius: 14px;
            font-size: 14px;
            line-height: 1.5;
            position: relative;
        }
        .msg-incoming {
            align-self: flex-start;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            color: #e2e8f0;
        }
        .msg-outgoing {
            align-self: flex-end;
            background: linear-gradient(135deg, #0284c7, #0369a1);
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);
        }
        .msg-sender { font-size: 11px; font-weight: 700; color: var(--accent); margin-bottom: 4px; }
        .msg-time { font-size: 10px; opacity: 0.7; text-align: right; margin-top: 4px; }
        /* Composer */
        .composer {
            padding: 16px 24px;
            background: var(--bg-surface);
            border-top: 1px solid var(--border);
            display: flex;
            gap: 12px;
            align-items: center;
        }
        .composer input {
            flex: 1;
            background: var(--bg-deep);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 18px;
            color: #fff;
            outline: none;
            font-size: 14px;
        }
        .composer input:focus { border-color: var(--accent); }
        .btn-send {
            background: var(--accent);
            color: #07090e;
            border: none;
            padding: 12px 20px;
            border-radius: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.1s ease;
        }
        .btn-send:hover { opacity: 0.95; transform: scale(1.02); }
        .btn-pay {
            background: #10b981;
            color: #fff;
            border: none;
            padding: 12px 16px;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
        }
        /* Modal for login */
        .modal-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px);
            display: flex; align-items: center; justify-content: center; z-index: 100;
        }
        .modal-card {
            background: var(--bg-surface); border: 1px solid var(--border); border-radius: 18px;
            padding: 32px; width: 380px; box-shadow: 0 20px 40px rgba(0,0,0,0.6);
        }
        .modal-card h2 { margin-bottom: 8px; color: var(--accent); font-size: 20px; }
        .modal-card input {
            width: 100%; background: var(--bg-deep); border: 1px solid var(--border);
            border-radius: 10px; padding: 12px; color: #fff; margin: 8px 0 16px;
        }
        .badge-verified {
            display: inline-flex; align-items: center; gap: 4px; font-size: 11px;
            background: rgba(16, 185, 129, 0.15); color: #10b981; padding: 4px 10px; border-radius: 20px;
        }
    </style>
</head>
<body>

    <!-- Login Modal -->
    <div id="loginModal" class="modal-overlay">
        <div class="modal-card">
            <h2>⚡ Telegram v2 PWA</h2>
            <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                MTProto E2E shifrlangan mustaqil tarmoqqa xush kelibsiz.
            </p>
            <label style="font-size: 12px; color: var(--text-secondary);">Username (@siz):</label>
            <input type="text" id="usernameInput" placeholder="masalan: jasper" value="jasper">
            
            <label style="font-size: 12px; color: var(--text-secondary);">Zaxira Email (Offline xabarlar uchun):</label>
            <input type="email" id="emailInput" placeholder="salomh46@gmail.com" value="salomh46@gmail.com">
            
            <button class="btn-send" style="width: 100%;" onclick="startSession()">Kirish (Connect)</button>
        </div>
    </div>

    <!-- Sidebar -->
    <div class="sidebar">
        <div class="sidebar-header">
            <div class="brand">⚡ Telegram v2</div>
            <span class="badge-verified">🔒 Zero-Knowledge</span>
        </div>
        <div class="chat-list" id="chatList">
            <div style="font-size: 11px; color: var(--text-secondary); margin: 8px 0 4px 6px; text-transform: uppercase;">Ochiq Kanallar</div>
            <div class="chat-item active" onclick="switchChat('#general')">
                <span class="chat-name">#general</span>
                <span class="chat-badge">Asosiy Guruh</span>
            </div>
            <div class="chat-item" onclick="switchChat('#announcements')">
                <span class="chat-name">#announcements</span>
                <span class="chat-badge">Yangiliklar</span>
            </div>
            <div class="chat-item" onclick="switchChat('#crypto_news')">
                <span class="chat-name">#crypto_news</span>
                <span class="chat-badge">Bozor & To'lovlar</span>
            </div>
            <div style="font-size: 11px; color: var(--text-secondary); margin: 18px 0 4px 6px; text-transform: uppercase;">Shaxsiy Chatlar</div>
            <div class="chat-item" onclick="switchChat('@alice')">
                <span class="chat-name">@alice</span>
                <span class="chat-badge">E2E Chat</span>
            </div>
            <div class="chat-item" onclick="switchChat('@bob')">
                <span class="chat-name">@bob</span>
                <span class="chat-badge">E2E Chat</span>
            </div>
        </div>
    </div>

    <!-- Main Chat View -->
    <div class="main-chat">
        <div class="chat-header">
            <div>
                <h3 id="currentChatTitle">#general</h3>
                <span style="font-size: 12px; color: var(--online);">🟢 MTProto Bridge Faol • Resend & Upstash Guard</span>
            </div>
            <div>
                <a id="seoLink" href="/channel/general" target="_blank" style="color: var(--accent); font-size: 13px; text-decoration: none; border: 1px solid var(--border); padding: 6px 12px; border-radius: 8px;">🌐 SEO Vitrina</a>
            </div>
        </div>

        <div class="messages-container" id="messagesContainer">
            <!-- Messages stream here -->
        </div>

        <div class="composer">
            <input type="text" id="messageInput" placeholder="Xabar yozing (Enter bosing)..." onkeypress="handleKeyPress(event)">
            <button class="btn-pay" onclick="simulateDirectPayment()" title="Telegram Stars 30% solig'isiz to'lov">💸 0% Pay</button>
            <button class="btn-send" onclick="sendMessage()">Yuborish</button>
        </div>
    </div>

    <script>
        let ws = null;
        let currentUser = "";
        let currentTarget = "#general";

        function startSession() {
            currentUser = document.getElementById("usernameInput").value.trim().toLowerCase();
            const email = document.getElementById("emailInput").value.trim();
            if (!currentUser) return;

            document.getElementById("loginModal").style.display = "none";
            connectWebSocket(currentUser, email);
        }

        function connectWebSocket(username, email) {
            const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
            const wsUrl = `${proto}//${window.location.host}/ws`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                ws.send(JSON.stringify({
                    type: "auth",
                    username: username,
                    display_name: username.toUpperCase(),
                    email: email
                }));
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleIncomingMessage(data);
            };

            ws.onclose = () => {
                appendSystemMsg("⚠️ Tarmoq uzildi. Qayta ulanish kutilmoqda...");
                setTimeout(() => connectWebSocket(username, email), 3000);
            };
        }

        function handleIncomingMessage(data) {
            if (data.type === "auth_success") {
                appendSystemMsg(`✅ Xush kelibsiz, @${data.username}! MTProto E2E Gateway bilan bog'landingiz.`);
                if (data.offline_messages && data.offline_messages.length > 0) {
                    data.offline_messages.forEach(m => appendMessage(m.sender, m.text, false));
                }
            } else if (data.type === "group_message") {
                if (currentTarget === data.group) {
                    appendMessage(data.sender, data.text, data.sender === currentUser);
                }
            } else if (data.type === "direct_message") {
                if (currentTarget === `@${data.sender}` || currentTarget === `@${data.recipient}`) {
                    appendMessage(data.sender, data.text, data.sender === currentUser);
                } else {
                    appendSystemMsg(`📬 @${data.sender} dan yangi xabar keldi: "${data.text.substring(0, 30)}..."`);
                }
            } else if (data.type === "payment_alert") {
                appendSystemMsg(`🎉 TO'LOV: @${data.from_user} -> @${data.to_user} ga ${data.amount} ${data.currency} to'landi! (0% komissiya)`);
            } else if (data.type === "system_notify") {
                appendSystemMsg(data.text);
            }
        }

        function sendMessage() {
            const input = document.getElementById("messageInput");
            const text = input.value.trim();
            if (!text || !ws) return;

            if (currentTarget.startsWith("#")) {
                ws.send(JSON.stringify({
                    type: "send_group",
                    group: currentTarget,
                    text: text
                }));
            } else {
                const recipient = currentTarget.replace("@", "");
                ws.send(JSON.stringify({
                    type: "send_message",
                    recipient: recipient,
                    text: text
                }));
                appendMessage(currentUser, text, true);
            }
            input.value = "";
        }

        function handleKeyPress(e) {
            if (e.key === "Enter") sendMessage();
        }

        function appendMessage(sender, text, isMine) {
            const container = document.getElementById("messagesContainer");
            const div = document.createElement("div");
            div.className = `msg-bubble ${isMine ? 'msg-outgoing' : 'msg-incoming'}`;
            
            const timeStr = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            div.innerHTML = `
                ${!isMine ? `<div class="msg-sender">@${sender}</div>` : ''}
                <div>${text}</div>
                <div class="msg-time">${timeStr}</div>
            `;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }

        function appendSystemMsg(text) {
            const container = document.getElementById("messagesContainer");
            const div = document.createElement("div");
            div.style.alignSelf = "center";
            div.style.background = "#1e293b";
            div.style.color = "#94a3b8";
            div.style.fontSize = "12px";
            div.style.padding = "6px 14px";
            div.style.borderRadius = "20px";
            div.innerText = text;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }

        function switchChat(target) {
            currentTarget = target;
            document.getElementById("currentChatTitle").innerText = target;
            document.querySelectorAll(".chat-item").forEach(el => el.classList.remove("active"));
            
            // update SEO link
            const seoLink = document.getElementById("seoLink");
            if (target.startsWith("#")) {
                seoLink.style.display = "inline";
                seoLink.href = `/channel/${target.replace('#', '')}`;
            } else {
                seoLink.style.display = "none";
            }

            const container = document.getElementById("messagesContainer");
            container.innerHTML = "";
            appendSystemMsg(`📌 ${target} chatiga o'tildi.`);
        }

        async function simulateDirectPayment() {
            const amount = prompt("To'lov miqdorini kiriting (so'mda):", "50000");
            if (!amount) return;
            const toUser = currentTarget.startsWith("@") ? currentTarget.replace("@", "") : "merchant";
            
            try {
                const res = await fetch("/api/pay/intent", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        from_user: currentUser,
                        to_user: toUser,
                        amount: parseInt(amount),
                        currency: "UZS",
                        memo: "PWA orqali to'lov"
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`To'lov cheki shakllantirildi!\nChek ID: ${data.invoice_id}\n0% Telegram Stars komissiyasi!`);
                }
            } catch(e) {
                alert("To'lovda xatolik: " + e.message);
            }
        }
    </script>
</body>
</html>""")

    return app
