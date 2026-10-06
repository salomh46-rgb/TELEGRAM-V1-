"""
Telegram v1 Async TCP Relay Server (MTProto Core).
High-concurrency server handling cryptographic handshakes, multi-client routing,
offline message synchronization, and E2E Secret Chat relaying.
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional

from telegram_v1.crypto.dh import DiffieHellmanKeyExchange
from telegram_v1.protocol.framing import TCPFraming
from telegram_v1.protocol.tl_schema import (
    TLPacket,
    TLType,
    make_dh_resp,
    make_dh_ack,
)
from telegram_v1.server.session import ClientSession
from telegram_v1.server.storage import MessageStorage

logger = logging.getLogger("telegram_v1.server")


class TelegramServer:
    """
    Core MTProto v1 relay server.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8443):
        self.host = host
        self.port = port
        self.storage = MessageStorage()
        # username -> active ClientSession
        self.active_sessions: Dict[str, ClientSession] = {}
        self._server: Optional[asyncio.Server] = None
        self._running = False

    async def start(self) -> None:
        """Starts the TCP server loop."""
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self._running = True
        logger.info(f"⚡ Telegram v1 MTProto Server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stops the server and disconnects clients."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for session in list(self.active_sessions.values()):
            await session.close()
        self.active_sessions.clear()
        logger.info("Telegram v1 Server stopped cleanly.")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        session_id = str(uuid.uuid4())[:8]
        session = ClientSession(reader, writer, session_id)
        logger.info(f"[*] New connection from {session.peer_address} (session: {session_id})")

        try:
            # Phase 1: Cryptographic Diffie-Hellman Handshake
            await self._perform_handshake(session)

            # Phase 2: Encrypted Messaging Loop
            await self._message_loop(session)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            logger.info(f"[-] Client {session.peer_address} disconnected abruptly.")
        except Exception as e:
            logger.error(f"[!] Error in session {session_id}: {e}", exc_info=True)
        finally:
            await self._cleanup_session(session)

    async def _perform_handshake(self, session: ClientSession) -> None:
        """Executes Diffie-Hellman Key Exchange to derive shared AuthKey."""
        # 1. Wait for DH_REQ from client
        raw_frame = await TCPFraming.read_frame(session.reader)
        if not raw_frame:
            return
        packet = TLPacket.from_bytes(raw_frame)
        if packet.type != TLType.DH_REQ:
            raise ValueError(f"Expected DH_REQ, received: {packet.type}")

        # 2. Server generates DH parameters
        dh = DiffieHellmanKeyExchange()
        resp_packet = make_dh_resp(dh.p, dh.g, dh.public_key)
        await session.send_raw_packet(resp_packet)

        # 3. Wait for DH_FINISH containing client's public key
        raw_finish = await TCPFraming.read_frame(session.reader)
        if not raw_finish:
            return
        finish_packet = TLPacket.from_bytes(raw_finish)
        if finish_packet.type != TLType.DH_FINISH:
            raise ValueError(f"Expected DH_FINISH, received: {finish_packet.type}")

        client_pub_int = int(finish_packet.data["client_public_key"], 16)
        session.auth_key = dh.compute_shared_key(client_pub_int)
        session.auth_key_id = DiffieHellmanKeyExchange.compute_auth_key_id(session.auth_key)
        session.handshake_complete = True

        # 4. Send DH_ACK
        ack_packet = make_dh_ack(session.auth_key_id.hex())
        await session.send_raw_packet(ack_packet)
        logger.info(f"[+] DH Handshake successful with {session.peer_address}. AuthKeyId: {session.auth_key_id.hex()}")

    async def _message_loop(self, session: ClientSession) -> None:
        """Processes encrypted incoming packets from client."""
        while self._running:
            raw_frame = await TCPFraming.read_frame(session.reader)
            if not raw_frame:
                break

            container = TLPacket.from_bytes(raw_frame)
            if container.type != TLType.ENCRYPTED_CONTAINER:
                logger.warning(f"Unexpected unencrypted packet after handshake: {container.type}")
                continue

            inner_packet = session.decrypt_container(container)
            await self._dispatch_packet(session, inner_packet)

    async def _dispatch_packet(self, session: ClientSession, packet: TLPacket) -> None:
        """Routes decrypted packets to appropriate handlers."""
        ptype = packet.type

        if ptype == TLType.AUTH_LOGIN:
            await self._handle_auth_login(session, packet)
        elif ptype == TLType.TEXT_MESSAGE:
            await self._handle_text_message(session, packet)
        elif ptype == TLType.GROUP_MESSAGE:
            await self._handle_group_message(session, packet)
        elif ptype in (TLType.SECRET_CHAT_REQUEST, TLType.SECRET_CHAT_ACCEPT, TLType.SECRET_CHAT_ENCRYPTED):
            await self._handle_secret_chat_relay(session, packet)
        elif ptype == TLType.USER_LIST_REQ:
            await self._handle_user_list(session)
        elif ptype == TLType.SYNC_REQ:
            await self._handle_sync(session)

    async def _handle_auth_login(self, session: ClientSession, packet: TLPacket) -> None:
        username = packet.data["username"].strip().lower()
        display_name = packet.data.get("display_name", username)

        session.username = username
        session.display_name = display_name
        self.active_sessions[username] = session
        self.storage.register_user(username, display_name)

        logger.info(f"[👤 AUTH] User @{username} ({display_name}) signed in.")

        # Confirm auth
        await session.send_encrypted(TLPacket(type=TLType.AUTH_SUCCESS, data={"username": username, "status": "online"}))

        # Check and deliver pending offline messages
        pending_messages = self.storage.retrieve_and_clear_offline_messages(username)
        if pending_messages:
            logger.info(f"[📦 SYNC] Delivering {len(pending_messages)} offline messages to @{username}")
            for msg in pending_messages:
                await session.send_encrypted(TLPacket(type=TLType.TEXT_MESSAGE, data=msg))

        # Broadcast online notification to others
        await self._broadcast_system(f"🔔 @{username} ({display_name}) tarmoqqa kirdi.", exclude_username=username)

    async def _handle_text_message(self, session: ClientSession, packet: TLPacket) -> None:
        recipient = packet.data.get("recipient", "").strip().lower()
        sender = session.username or "anonymous"
        packet.data["sender"] = sender

        target_session = self.active_sessions.get(recipient)
        if target_session and target_session.handshake_complete:
            # Deliver in real-time
            await target_session.send_encrypted(packet)
            logger.info(f"[📨 MSG] @{sender} -> @{recipient}: Delivered live.")
        else:
            # Queue in offline inbox
            self.storage.queue_offline_message(recipient, packet.data)
            logger.info(f"[📬 OFFLINE] @{sender} -> @{recipient}: Queued in offline inbox.")

    async def _handle_group_message(self, session: ClientSession, packet: TLPacket) -> None:
        group = packet.data.get("group", "#general")
        sender = session.username or "anonymous"
        packet.data["sender"] = sender

        members = self.storage.get_group_members(group)
        for member in members:
            if member == sender:
                continue
            target_session = self.active_sessions.get(member)
            if target_session:
                await target_session.send_encrypted(packet)

        logger.info(f"[👥 GROUP] @{sender} in {group}: Broadcasted to {len(members)-1} members.")

    async def _handle_secret_chat_relay(self, session: ClientSession, packet: TLPacket) -> None:
        """Relays End-to-End encrypted Secret Chat messages without server inspection."""
        recipient = packet.data.get("recipient", "").strip().lower()
        sender = session.username or "anonymous"
        packet.data["sender"] = sender

        target_session = self.active_sessions.get(recipient)
        if target_session:
            await target_session.send_encrypted(packet)
            logger.info(f"[🔒 SECRET CHAT] Relayed {packet.type} @{sender} -> @{recipient} (Zero Knowledge).")
        else:
            # Inform sender that recipient is currently offline
            await session.send_encrypted(
                TLPacket(
                    type=TLType.SYSTEM_NOTIFY,
                    data={"text": f"⚠️ @{recipient} oflayn. Maxfiy chat faqat ikkala tomon onlayn bo'lganda ishlaydi."},
                )
            )

    async def _handle_user_list(self, session: ClientSession) -> None:
        users = [
            {"username": u, "display_name": s.display_name or u, "status": "online"}
            for u, s in self.active_sessions.items()
        ]
        await session.send_encrypted(TLPacket(type=TLType.USER_LIST_RESP, data={"users": users}))

    async def _handle_sync(self, session: ClientSession) -> None:
        if not session.username:
            return
        pending = self.storage.retrieve_and_clear_offline_messages(session.username)
        await session.send_encrypted(TLPacket(type=TLType.SYNC_RESP, data={"messages": pending}))

    async def _broadcast_system(self, text: str, exclude_username: Optional[str] = None) -> None:
        packet = TLPacket(type=TLType.SYSTEM_NOTIFY, data={"text": text})
        for uname, session in self.active_sessions.items():
            if uname != exclude_username:
                try:
                    await session.send_encrypted(packet)
                except Exception:
                    pass

    async def _cleanup_session(self, session: ClientSession) -> None:
        if session.username and session.username in self.active_sessions:
            del self.active_sessions[session.username]
            logger.info(f"[👋 QUIT] @{session.username} disconnected.")
            await self._broadcast_system(f"📴 @{session.username} tarmoqdan chiqdi.")
        await session.close()
