"""Read API keys: encrypted rows in `secrets` (set from the dashboard) with env-var fallback."""
import os
import time

from . import crypto, db
from .log import log

_ENV = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "elevenlabs_api_key": "ELEVENLABS_API_KEY",
    "runpod_api_key": "RUNPOD_API_KEY",
    "tiktok_client_key": "TIKTOK_CLIENT_KEY",
    "tiktok_client_secret": "TIKTOK_CLIENT_SECRET",
    "resend_api_key": "RESEND_API_KEY",
}
_cache: dict[str, tuple[float, str | None]] = {}
TTL = 60


def get(key: str) -> str | None:
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < TTL:
        return hit[1]
    val = None
    try:
        row = db.select("secrets", {"key": key}, single=True)
        if row:
            val = crypto.decrypt(row["ciphertext"])
    except Exception as e:
        log.warning(f"secret {key}: {e}")
    if not val:
        val = os.environ.get(_ENV.get(key, key.upper())) or None
    _cache[key] = (now, val)
    return val


def clear_cache() -> None:
    _cache.clear()
