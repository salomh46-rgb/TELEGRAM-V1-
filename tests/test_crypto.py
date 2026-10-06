"""
Unit tests for cryptographic components of Telegram v1.
"""

import pytest
from telegram_v1.crypto.dh import DiffieHellmanKeyExchange
from telegram_v1.crypto.cipher import MTProtoCipher


def test_diffie_hellman_shared_secret():
    """Verify that Alice and Bob compute the exact same AuthKey."""
    alice_dh = DiffieHellmanKeyExchange()
    bob_dh = DiffieHellmanKeyExchange()

    alice_key = alice_dh.compute_shared_key(bob_dh.public_key)
    bob_key = bob_dh.compute_shared_key(alice_dh.public_key)

    assert alice_key == bob_key
    assert len(alice_key) == 32

    # Check AuthKeyID calculation
    alice_key_id = DiffieHellmanKeyExchange.compute_auth_key_id(alice_key)
    bob_key_id = DiffieHellmanKeyExchange.compute_auth_key_id(bob_key)
    assert alice_key_id == bob_key_id
    assert len(alice_key_id) == 8


def test_mtproto_cipher_encryption_decryption():
    """Verify MTProto v1 AES-256-CBC encryption and msg_key integrity."""
    auth_key = b"12345678901234567890123456789012"  # 32 bytes
    plaintext = b"Hello Nikolai Durov! This is Telegram v1."

    # Encrypt (Client -> Server)
    msg_key, ciphertext = MTProtoCipher.encrypt(plaintext, auth_key, is_client=True)
    assert len(msg_key) == 16
    assert len(ciphertext) > 0
    assert ciphertext != plaintext

    # Decrypt (Server receives Client payload)
    decrypted = MTProtoCipher.decrypt(ciphertext, msg_key, auth_key, is_client=True)
    assert decrypted == plaintext


def test_mtproto_cipher_tamper_detection():
    """Verify that altered ciphertext or wrong auth_key triggers integrity failure."""
    auth_key = b"12345678901234567890123456789012"
    wrong_key = b"99999999999999999999999999999999"
    plaintext = b"Sensitive secret payload"

    msg_key, ciphertext = MTProtoCipher.encrypt(plaintext, auth_key, is_client=True)

    # Attempt decrypt with wrong key
    with pytest.raises(Exception):
        MTProtoCipher.decrypt(ciphertext, msg_key, wrong_key, is_client=True)

    # Attempt decrypt with tampered ciphertext
    tampered = bytearray(ciphertext)
    tampered[0] ^= 0xFF
    with pytest.raises(Exception):
        MTProtoCipher.decrypt(bytes(tampered), msg_key, auth_key, is_client=True)
