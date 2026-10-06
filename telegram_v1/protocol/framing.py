"""
TCP Framing layer for Telegram v1.
Ensures message boundary delineation and integrity over raw TCP streams.
Packet format:
[4 bytes: length (big-endian)] [N bytes: payload] [4 bytes: CRC32 checksum]
"""

import asyncio
import struct
import zlib
from typing import Optional


class TCPFraming:
    """
    Handles serialization and framing of packets over TCP streams with CRC32 integrity checks.
    """

    @staticmethod
    def pack(payload: bytes) -> bytes:
        """
        Encapsulates payload into a framed packet:
        [length: 4B] + payload + [crc32: 4B]
        """
        length = len(payload)
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        header = struct.pack(">I", length)
        footer = struct.pack(">I", checksum)
        return header + payload + footer

    @staticmethod
    async def read_frame(reader: asyncio.StreamReader) -> Optional[bytes]:
        """
        Asynchronously reads a single frame from an asyncio.StreamReader.
        Returns the payload bytes, or None if EOF is reached.
        Raises ValueError if CRC32 check fails.
        """
        # Read 4-byte length header
        try:
            length_bytes = await reader.readexactly(4)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            return None

        (length,) = struct.unpack(">I", length_bytes)
        if length > 10 * 1024 * 1024:  # 10MB safety sanity limit
            raise ValueError(f"Packet length exceeds safety limit: {length} bytes")

        # Read exact payload
        try:
            payload = await reader.readexactly(length)
        except asyncio.IncompleteReadError:
            return None

        # Read 4-byte CRC32 footer
        try:
            footer_bytes = await reader.readexactly(4)
        except asyncio.IncompleteReadError:
            return None

        (expected_checksum,) = struct.unpack(">I", footer_bytes)
        actual_checksum = zlib.crc32(payload) & 0xFFFFFFFF

        if actual_checksum != expected_checksum:
            raise ValueError(f"CRC32 mismatch: expected {expected_checksum:#010x}, got {actual_checksum:#010x}")

        return payload
