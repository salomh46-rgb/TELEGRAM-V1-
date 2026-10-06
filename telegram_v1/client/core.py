"""
Telegram v1 Async Client Engine.
Handles Diffie-Hellman cryptographic handshake with server,
message framing, MTProto v1 encryption/decryption, and End-to-End Secret Chats.
"""

import asyncio
import logging
import uuid
from typing import Callable, Dict, List, Optional

from telegram_v1.crypto.cipher import MTProtoCipher
from telegram_v1.crypto.dh import DiffieHellmanKeyExchange
from telegram_v1.protocol.framing import TCPFraming
from telegram_v1.protocol.tl_schema import (
    TLPacket,
    TLType,
    make_dh_req,
    make_dh_finish,
    make_encrypted_container,
    make_text_message,
    make_group_message,
)

logger = logging.getLogger("telegram_v1.client")


class TelegramClient:
    """
    High-level MTProto v1 Client.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8443):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

        # Server-Client MTProto session keys
        self.auth_key: Optional[bytes] = None
        self.auth_key_id: Optional[bytes] = None

        # User profile
        self.username: Optional[str] = None
        self.display_name: Optional[str] = None
        self.is_connected = False

        # E2E Secret Chats: recipient_username -> { "dh": DiffieHellmanKeyExchange, "secret_key": bytes }
        self.secret_chats: Dict[str, dict] = {}

        # Callbacks
        self.on_message_callback: Optional[Callable[[dict], None]] = None
        self.on_group_callback: Optional[Callable[[dict], None]] = None
        self.on_secret_callback: Optional[Callable[[dict], None]] = None
        self.on_notification_callback: Optional[Callable[[str], None]] = None
        self.on_user_list_callback: Optional[Callable[[List[dict]], None]] = None

        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Establishes TCP connection and performs MTProto DH handshake."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        await self._perform_handshake()
        self.is_connected = True
        self._listener_task = asyncio.create_task(self._listen_incoming())

    async def disconnect(self) -> None:
        """Closes connection gracefully."""
        self.is_connected = False
        if self._listener_task:
            self._listener_task.cancel()
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

    async def _perform_handshake(self) -> None:
        """Executes client-side Diffie-Hellman handshake."""
        # 1. Send DH_REQ
        await self._send_raw(make_dh_req())

        # 2. Receive DH_RESP from server
        raw_resp = await TCPFraming.read_frame(self.reader)
        if not raw_resp:
            raise ConnectionError("Server closed connection during DH handshake")
        resp_packet = TLPacket.from_bytes(raw_resp)
        if resp_packet.type != TLType.DH_RESP:
            raise ValueError(f"Expected DH_RESP, got {resp_packet.type}")

        p = int(resp_packet.data["p"], 16)
        g = resp_packet.data["g"]
        server_pub = int(resp_packet.data["server_public_key"], 16)

        # 3. Generate client DH keypair & send public key
        dh = DiffieHellmanKeyExchange(prime=p, generator=g)
        await self._send_raw(make_dh_finish(dh.public_key))

        # 4. Compute AuthKey & AuthKeyId
        self.auth_key = dh.compute_shared_key(server_pub)
        self.auth_key_id = DiffieHellmanKeyExchange.compute_auth_key_id(self.auth_key)

        # 5. Receive DH_ACK
        raw_ack = await TCPFraming.read_frame(self.reader)
        if not raw_ack:
            raise ConnectionError("Server closed connection before DH_ACK")
        ack_packet = TLPacket.from_bytes(raw_ack)
        if ack_packet.type != TLType.DH_ACK:
            raise ValueError(f"Expected DH_ACK, got {ack_packet.type}")

        expected_id_hex = self.auth_key_id.hex()
        if ack_packet.data["auth_key_id"] != expected_id_hex:
            raise ValueError("AuthKeyId mismatch between client and server!")

        logger.info(f"Connected securely to Telegram v1 server. AuthKeyId: {expected_id_hex}")

    async def _send_raw(self, packet: TLPacket) -> None:
        frame = TCPFraming.pack(packet.to_bytes())
        self.writer.write(frame)
        await self.writer.drain()

    async def send_encrypted(self, packet: TLPacket) -> None:
        """Encrypts packet with session AuthKey and sends in MTProto container."""
        if not self.auth_key or not self.auth_key_id:
            raise RuntimeError("Cannot send encrypted: AuthKey not established")

        plaintext = packet.to_bytes()
        # Client encrypts with is_client=True
        msg_key, ciphertext = MTProtoCipher.encrypt(plaintext, self.auth_key, is_client=True)

        container = make_encrypted_container(
            auth_key_id_hex=self.auth_key_id.hex(),
            msg_key_hex=msg_key.hex(),
            ciphertext_hex=ciphertext.hex(),
        )
        await self._send_raw(container)

    async def login(self, username: str, display_name: str) -> None:
        """Authenticates client identity with server."""
        self.username = username
        self.display_name = display_name
        login_packet = TLPacket(
            type=TLType.AUTH_LOGIN,
            data={"username": username, "display_name": display_name},
        )
        await self.send_encrypted(login_packet)

    async def send_message(self, recipient: str, text: str) -> str:
        """Sends a 1-to-1 direct message."""
        msg_id = str(uuid.uuid4())[:8]
        packet = make_text_message(msg_id, self.username or "me", recipient, text)
        await self.send_encrypted(packet)
        return msg_id

    async def send_group_message(self, text: str, group: str = "#general") -> str:
        """Sends a message to a public or group channel."""
        msg_id = str(uuid.uuid4())[:8]
        packet = make_group_message(msg_id, self.username or "me", group, text)
        await self.send_encrypted(packet)
        return msg_id

    async def request_user_list(self) -> None:
        """Requests list of online users."""
        await self.send_encrypted(TLPacket(type=TLType.USER_LIST_REQ, data={}))

    # --- End-to-End Secret Chat Protocol ---

    async def start_secret_chat(self, peer_username: str) -> None:
        """
        Initiates an End-to-End encrypted Secret Chat with peer.
        Generates a fresh, independent DH keypair for direct E2E encryption.
        """
        peer = peer_username.strip().lower()
        dh = DiffieHellmanKeyExchange()
        self.secret_chats[peer] = {
            "dh": dh,
            "secret_key": None,
            "status": "pending_outgoing",
        }

        # Send peer our public key via server relay
        req_packet = TLPacket(
            type=TLType.SECRET_CHAT_REQUEST,
            data={
                "recipient": peer,
                "p": hex(dh.p),
                "g": dh.g,
                "client_public_key": hex(dh.public_key),
            },
        )
        await self.send_encrypted(req_packet)
        if self.on_notification_callback:
            self.on_notification_callback(f"🔒 @{peer} bilan Maxfiy Chat (E2E) so'rovi yuborildi...")

    async def send_secret_message(self, recipient: str, text: str) -> None:
        """Sends an E2E encrypted message to peer (Zero-knowledge for server)."""
        peer = recipient.strip().lower()
        chat_info = self.secret_chats.get(peer)
        if not chat_info or not chat_info.get("secret_key"):
            raise ValueError(f"@{peer} bilan faol Maxfiy Chat mavjud emas. Avval /secret {peer} qiling.")

        secret_key = chat_info["secret_key"]
        # Encrypt with peer's dedicated E2E key
        msg_key, ciphertext = MTProtoCipher.encrypt(text.encode("utf-8"), secret_key, is_client=True)

        relay_packet = TLPacket(
            type=TLType.SECRET_CHAT_ENCRYPTED,
            data={
                "recipient": peer,
                "msg_key": msg_key.hex(),
                "ciphertext": ciphertext.hex(),
            },
        )
        await self.send_encrypted(relay_packet)

    # --- Incoming Message Listener Loop ---

    async def _listen_incoming(self) -> None:
        """Continuously reads and dispatches packets from server."""
        try:
            while self.is_connected:
                raw_frame = await TCPFraming.read_frame(self.reader)
                if not raw_frame:
                    break

                container = TLPacket.from_bytes(raw_frame)
                if container.type != TLType.ENCRYPTED_CONTAINER:
                    continue

                # Decrypt server container
                data = container.data
                msg_key = bytes.fromhex(data["msg_key"])
                ciphertext = bytes.fromhex(data["ciphertext"])
                decrypted_bytes = MTProtoCipher.decrypt(ciphertext, msg_key, self.auth_key, is_client=False)
                packet = TLPacket.from_bytes(decrypted_bytes)

                await self._handle_packet(packet)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in client listener: {e}")
            if self.on_notification_callback:
                self.on_notification_callback(f"⚠️ Aloqa uzildi: {e}")

    async def _handle_packet(self, packet: TLPacket) -> None:
        ptype = packet.type

        if ptype == TLType.TEXT_MESSAGE:
            if self.on_message_callback:
                self.on_message_callback(packet.data)

        elif ptype == TLType.GROUP_MESSAGE:
            if self.on_group_callback:
                self.on_group_callback(packet.data)

        elif ptype == TLType.SYSTEM_NOTIFY:
            if self.on_notification_callback:
                self.on_notification_callback(packet.data.get("text", ""))

        elif ptype == TLType.USER_LIST_RESP:
            if self.on_user_list_callback:
                self.on_user_list_callback(packet.data.get("users", []))

        elif ptype == TLType.SECRET_CHAT_REQUEST:
            await self._handle_incoming_secret_request(packet.data)

        elif ptype == TLType.SECRET_CHAT_ACCEPT:
            await self._handle_incoming_secret_accept(packet.data)

        elif ptype == TLType.SECRET_CHAT_ENCRYPTED:
            self._handle_incoming_secret_message(packet.data)

    async def _handle_incoming_secret_request(self, data: dict) -> None:
        sender = data["sender"]
        p = int(data["p"], 16)
        g = data["g"]
        peer_pub = int(data["client_public_key"], 16)

        # Peer requested secret chat. Generate our DH key
        dh = DiffieHellmanKeyExchange(prime=p, generator=g)
        shared_key = dh.compute_shared_key(peer_pub)

        self.secret_chats[sender] = {
            "dh": dh,
            "secret_key": shared_key,
            "status": "established",
        }

        # Send acceptance with our public key
        accept_packet = TLPacket(
            type=TLType.SECRET_CHAT_ACCEPT,
            data={
                "recipient": sender,
                "client_public_key": hex(dh.public_key),
            },
        )
        await self.send_encrypted(accept_packet)
        if self.on_notification_callback:
            self.on_notification_callback(f"🔒 @{sender} bilan E2E Maxfiy Chat o'rnatildi! (100% Shifrlangan)")

    async def _handle_incoming_secret_accept(self, data: dict) -> None:
        sender = data["sender"]
        chat_info = self.secret_chats.get(sender)
        if not chat_info or "dh" not in chat_info:
            return

        peer_pub = int(data["client_public_key"], 16)
        dh: DiffieHellmanKeyExchange = chat_info["dh"]
        shared_key = dh.compute_shared_key(peer_pub)

        chat_info["secret_key"] = shared_key
        chat_info["status"] = "established"

        if self.on_notification_callback:
            self.on_notification_callback(f"🔒 @{sender} bilan E2E Maxfiy Chat faollashdi! Endi /smsg {sender} bilan yozishingiz mumkin.")

    def _handle_incoming_secret_message(self, data: dict) -> None:
        sender = data["sender"]
        chat_info = self.secret_chats.get(sender)
        if not chat_info or not chat_info.get("secret_key"):
            return

        secret_key = chat_info["secret_key"]
        msg_key = bytes.fromhex(data["msg_key"])
        ciphertext = bytes.fromhex(data["ciphertext"])

        # Decrypt E2E payload (sender used is_client=True, so decrypt with is_client=True)
        decrypted_bytes = MTProtoCipher.decrypt(ciphertext, msg_key, secret_key, is_client=True)
        text = decrypted_bytes.decode("utf-8")

        if self.on_secret_callback:
            self.on_secret_callback({"sender": sender, "text": text})
