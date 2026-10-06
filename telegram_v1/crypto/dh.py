"""
Diffie-Hellman Key Exchange implementation for Telegram v1 (MTProto-lite).
Inspired by Nikolai Durov's original MTProto 1.0 cryptographic handshake.
"""

import hashlib
import secrets
from typing import Tuple

# RFC 3526 2048-bit MODP Group (Prime p and Generator g=2)
# Standard secure prime used across cryptographic protocols
DH_PRIME_2048_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)

DH_PRIME = int(DH_PRIME_2048_HEX, 16)
DH_GENERATOR = 2


class DiffieHellmanKeyExchange:
    """
    Manages Diffie-Hellman key exchange parameters and operations.
    """

    def __init__(self, prime: int = DH_PRIME, generator: int = DH_GENERATOR):
        self.p = prime
        self.g = generator
        # Generate private key: 2048-bit random integer
        self.private_key = secrets.randbelow(self.p - 3) + 2
        # Public key: A = g^a mod p
        self.public_key = pow(self.g, self.private_key, self.p)

    def compute_shared_key(self, peer_public_key: int) -> bytes:
        """
        Computes the shared master key K = (peer_public_key ^ private_key) mod p
        and derives a 256-bit AuthKey using SHA-256.
        """
        if not (1 < peer_public_key < self.p - 1):
            raise ValueError("Invalid peer public key (outside safe range)")

        shared_secret_int = pow(peer_public_key, self.private_key, self.p)
        # Convert integer to big-endian bytes
        shared_secret_bytes = shared_secret_int.to_bytes((self.p.bit_length() + 7) // 8, byteorder="big")
        
        # Derive 32-byte AuthKey via SHA-256 (MTProto AuthKey derivation)
        auth_key = hashlib.sha256(shared_secret_bytes).digest()
        return auth_key

    @staticmethod
    def compute_auth_key_id(auth_key: bytes) -> bytes:
        """
        Computes 8-byte auth_key_id from SHA-256(auth_key)[-8:].
        Used by Telegram to quickly identify which session key is being used.
        """
        return hashlib.sha256(auth_key).digest()[-8:]
