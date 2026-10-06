"""
Client session abstraction for Telegram v1 server.
Manages socket streams, cryptographic state, and user identities.
"""

import asyncio
from typing import Optional
from telegram_v1.crypto.cipher import MTProtoCipher
from telegram_v1.protocol.framing import TCPFraming
from telegram_v1.protocol.tl_schema import TLPacket, make_encrypted_container


class ClientSession:
    """
    Represents an active TCP connection to the Telegram v1 server.
    Tracks authentication, Diffie-Hellman AuthKey, and encryption state.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, session_id: str):
        self.reader = reader
        self.writer = writer
        self.session_id = session_id
        
        # Crypto state
        self.auth_key: Optional[bytes] = None
        self.auth_key_id: Optional[bytes] = None
        self.handshake_complete: bool = False

        # Identity state
        self.username: Optional[str] = None
        self.display_name: Optional[str] = None

    @property
    def peer_address(self) -> str:
        peer = self.writer.get_extra_info("peername")
        return f"{peer[0]}:{peer[1]}" if peer else "Unknown"

    async def send_raw_packet(self, packet: TLPacket) -> None:
        """Sends an unencrypted framed TL packet (used during DH handshake)."""
        payload = packet.to_bytes()
        frame = TCPFraming.pack(payload)
        self.writer.write(frame)
        await self.writer.drain()

    async def send_encrypted(self, packet: TLPacket) -> None:
        """
        Encrypts an inner TL packet using the session's AuthKey and sends it
        inside an MTProto encrypted container.
        """
        if not self.auth_key or not self.auth_key_id:
            raise RuntimeError("Cannot send encrypted packet: AuthKey not established")

        plaintext = packet.to_bytes()
        # Server encrypts with is_client=False
        msg_key, ciphertext = MTProtoCipher.encrypt(plaintext, self.auth_key, is_client=False)

        container = make_encrypted_container(
            auth_key_id_hex=self.auth_key_id.hex(),
            msg_key_hex=msg_key.hex(),
            ciphertext_hex=ciphertext.hex(),
        )
        await self.send_raw_packet(container)

    def decrypt_container(self, container_packet: TLPacket) -> TLPacket:
        """
        Decrypts an encrypted container received from the client.
        """
        if not self.auth_key:
            raise RuntimeError("AuthKey not initialized")

        data = container_packet.data
        msg_key = bytes.fromhex(data["msg_key"])
        ciphertext = bytes.fromhex(data["ciphertext"])

        # Server decrypts client message with is_client=True
        decrypted_bytes = MTProtoCipher.decrypt(ciphertext, msg_key, self.auth_key, is_client=True)
        return TLPacket.from_bytes(decrypted_bytes)

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
