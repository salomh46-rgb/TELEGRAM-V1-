"""
MTProto v1 inspired symmetric encryption and message verification engine.
Uses AES-256-CBC with SHA-256 message keys (msg_key) for integrity verification.
"""

import hashlib
import os
from typing import Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class MTProtoCipher:
    """
    Handles MTProto v1 style symmetric encryption and decryption.
    Derives per-message AES keys and IVs using auth_key and msg_key.
    """

    @staticmethod
    def derive_keys(auth_key: bytes, msg_key: bytes, is_client: bool) -> Tuple[bytes, bytes]:
        """
        Derives a 32-byte AES key and 16-byte IV from auth_key and msg_key.
        Mirrors Telegram MTProto's key derivation formula.
        """
        x = 0 if is_client else 8
        sha256_a = hashlib.sha256(msg_key + auth_key[x : x + 36]).digest()
        sha256_b = hashlib.sha256(auth_key[x + 40 : x + 76] + msg_key).digest() if len(auth_key) >= 76 else hashlib.sha256(auth_key + msg_key).digest()

        # aes_key = sha256_a[0:8] + sha256_b[8:24] + sha256_a[24:32] (32 bytes)
        aes_key = sha256_a[:8] + sha256_b[8:24] + sha256_a[24:32]
        # aes_iv = sha256_b[0:8] + sha256_a[8:16] (16 bytes)
        aes_iv = sha256_b[:8] + sha256_a[8:16]

        return aes_key, aes_iv

    @staticmethod
    def pad(data: bytes, block_size: int = 16) -> bytes:
        """PKCS7 padding"""
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def unpad(data: bytes) -> bytes:
        """PKCS7 unpadding"""
        if not data:
            raise ValueError("Empty data cannot be unpadded")
        pad_len = data[-1]
        if pad_len < 1 or pad_len > 16:
            raise ValueError("Invalid PKCS7 padding length")
        if data[-pad_len:] != bytes([pad_len] * pad_len):
            raise ValueError("Corrupt PKCS7 padding bytes")
        return data[:-pad_len]

    @classmethod
    def encrypt(cls, plaintext: bytes, auth_key: bytes, is_client: bool = True) -> Tuple[bytes, bytes]:
        """
        Encrypts plaintext using MTProto v1 scheme:
        1. msg_key = SHA-256(auth_key[8:24] + plaintext)[:16]
        2. aes_key, aes_iv = derive_keys(auth_key, msg_key)
        3. ciphertext = AES_CBC(padded_plaintext)
        Returns: (msg_key, ciphertext)
        """
        padded = cls.pad(plaintext)
        msg_key = hashlib.sha256(auth_key[8:24] + padded).digest()[:16]
        aes_key, aes_iv = cls.derive_keys(auth_key, msg_key, is_client)

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()

        return msg_key, ciphertext

    @classmethod
    def decrypt(cls, ciphertext: bytes, msg_key: bytes, auth_key: bytes, is_client: bool = False) -> bytes:
        """
        Decrypts ciphertext and validates msg_key integrity:
        1. aes_key, aes_iv = derive_keys(auth_key, msg_key)
        2. padded_plaintext = AES_CBC_decrypt(ciphertext)
        3. expected_msg_key = SHA-256(auth_key[8:24] + padded_plaintext)[:16]
        4. Validate msg_key == expected_msg_key
        """
        aes_key, aes_iv = cls.derive_keys(auth_key, msg_key, is_client)

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        expected_msg_key = hashlib.sha256(auth_key[8:24] + padded).digest()[:16]
        if expected_msg_key != msg_key:
            raise ValueError("Integrity verification failed: msg_key mismatch (tampered or wrong key)")

        return cls.unpad(padded)
