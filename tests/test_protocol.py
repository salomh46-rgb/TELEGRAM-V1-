"""
Unit tests for protocol framing and Type Language (TL) schema.
"""

import asyncio
import pytest
from telegram_v1.protocol.framing import TCPFraming
from telegram_v1.protocol.tl_schema import (
    TLType,
    TLPacket,
    make_dh_req,
    make_text_message,
)


@pytest.mark.asyncio
async def test_tcp_framing_pack_and_read():
    payload = b"Sample Telegram TL binary packet data"
    packed_frame = TCPFraming.pack(payload)

    # Use asyncio.StreamReader to simulate TCP stream
    reader = asyncio.StreamReader()
    reader.feed_data(packed_frame)
    reader.feed_eof()

    read_payload = await TCPFraming.read_frame(reader)
    assert read_payload == payload


@pytest.mark.asyncio
async def test_tcp_framing_crc_tampering():
    payload = b"Tamper target"
    packed_frame = bytearray(TCPFraming.pack(payload))

    # Corrupt last byte (CRC32 footer)
    packed_frame[-1] ^= 0xAA

    reader = asyncio.StreamReader()
    reader.feed_data(bytes(packed_frame))
    reader.feed_eof()

    with pytest.raises(ValueError, match="CRC32 mismatch"):
        await TCPFraming.read_frame(reader)


def test_tl_packet_serialization():
    original = make_text_message("msg123", "alice", "bob", "Salom!")
    raw_bytes = original.to_bytes()

    restored = TLPacket.from_bytes(raw_bytes)
    assert restored.type == TLType.TEXT_MESSAGE
    assert restored.data["msg_id"] == "msg123"
    assert restored.data["sender"] == "alice"
    assert restored.data["recipient"] == "bob"
    assert restored.data["text"] == "Salom!"
