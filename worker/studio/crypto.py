"""AES-256-GCM helpers. Format: 'v1:' + base64(iv[12] || ciphertext || tag[16]). Shared with apps/web."""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from . import config


def _key() -> bytes:
    if not config.MASTER_KEY:
        raise RuntimeError("MASTER_KEY is not set")
    k = base64.b64decode(config.MASTER_KEY)
    if len(k) != 32:
        raise RuntimeError("MASTER_KEY must be 32 bytes (base64)")
    return k


def encrypt(plaintext: str) -> str:
    iv = os.urandom(12)
    ct = AESGCM(_key()).encrypt(iv, plaintext.encode(), None)
    return "v1:" + base64.b64encode(iv + ct).decode()


def decrypt(token: str) -> str:
    if not token.startswith("v1:"):
        raise ValueError("unknown ciphertext version")
    raw = base64.b64decode(token[3:])
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], None).decode()
