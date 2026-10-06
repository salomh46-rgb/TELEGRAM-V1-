"""
Type Language (TL) Schema for Telegram v1.
Defines MTProto-lite protocol packet types and serialization routines.
"""

import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


class TLType:
    # Handshake types
    DH_REQ = "dh_req"
    DH_RESP = "dh_resp"
    DH_FINISH = "dh_finish"
    DH_ACK = "dh_ack"

    # Transport container
    ENCRYPTED_CONTAINER = "encrypted_container"

    # Inner Payload types (encrypted)
    AUTH_LOGIN = "auth_login"
    AUTH_SUCCESS = "auth_success"
    AUTH_ERROR = "auth_error"
    
    TEXT_MESSAGE = "text_message"
    GROUP_MESSAGE = "group_message"
    
    # End-to-End Secret Chat
    SECRET_CHAT_REQUEST = "secret_chat_req"
    SECRET_CHAT_ACCEPT = "secret_chat_accept"
    SECRET_CHAT_ENCRYPTED = "secret_chat_encrypted"

    # Sync & State
    USER_LIST_REQ = "user_list_req"
    USER_LIST_RESP = "user_list_resp"
    SYNC_REQ = "sync_req"
    SYNC_RESP = "sync_resp"
    SYSTEM_NOTIFY = "system_notify"


@dataclass
class TLPacket:
    type: str
    data: Dict[str, Any]

    def to_bytes(self) -> bytes:
        """Serializes TL packet to UTF-8 encoded JSON bytes"""
        raw_dict = {"type": self.type, "data": self.data}
        return json.dumps(raw_dict, ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> "TLPacket":
        """Deserializes TL packet from UTF-8 bytes"""
        data = json.loads(raw_bytes.decode("utf-8"))
        return cls(type=data["type"], data=data.get("data", {}))


# Helper factories for clean construction
def make_dh_req() -> TLPacket:
    return TLPacket(type=TLType.DH_REQ, data={"nonce": time.time_ns()})


def make_dh_resp(p: int, g: int, server_public_key: int) -> TLPacket:
    return TLPacket(
        type=TLType.DH_RESP,
        data={
            "p": hex(p),
            "g": g,
            "server_public_key": hex(server_public_key),
        },
    )


def make_dh_finish(client_public_key: int) -> TLPacket:
    return TLPacket(
        type=TLType.DH_FINISH,
        data={"client_public_key": hex(client_public_key)},
    )


def make_dh_ack(auth_key_id_hex: str) -> TLPacket:
    return TLPacket(type=TLType.DH_ACK, data={"auth_key_id": auth_key_id_hex})


def make_encrypted_container(auth_key_id_hex: str, msg_key_hex: str, ciphertext_hex: str) -> TLPacket:
    return TLPacket(
        type=TLType.ENCRYPTED_CONTAINER,
        data={
            "auth_key_id": auth_key_id_hex,
            "msg_key": msg_key_hex,
            "ciphertext": ciphertext_hex,
        },
    )


def make_text_message(msg_id: str, sender: str, recipient: str, text: str) -> TLPacket:
    return TLPacket(
        type=TLType.TEXT_MESSAGE,
        data={
            "msg_id": msg_id,
            "sender": sender,
            "recipient": recipient,
            "text": text,
            "timestamp": time.time(),
        },
    )


def make_group_message(msg_id: str, sender: str, group: str, text: str) -> TLPacket:
    return TLPacket(
        type=TLType.GROUP_MESSAGE,
        data={
            "msg_id": msg_id,
            "sender": sender,
            "group": group,
            "text": text,
            "timestamp": time.time(),
        },
    )
