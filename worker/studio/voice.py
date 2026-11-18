"""ElevenLabs voiceover with character-level timestamps → word timings for synced captions."""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass

import httpx

from . import secrets, spend
from .services import NotConfigured, OutOfCredits, ServiceDown, set_status

API = "https://api.elevenlabs.io"
USD_PER_CHAR = 0.00022          # ≈ Creator plan ($22 / 100k chars); used for the cost ledger only


@dataclass
class Word:
    text: str
    start: float
    end: float


def _headers() -> dict:
    return {"xi-api-key": secrets.get("elevenlabs_api_key") or "proxy-injected", "Content-Type": "application/json"}


def _fail(r: httpx.Response) -> Exception:
    try:
        det = r.json().get("detail") or {}
    except Exception:
        det = {}
    status = (det.get("status") if isinstance(det, dict) else "") or ""
    msg = (det.get("message") if isinstance(det, dict) else str(det)) or r.text[:200]
    if status in ("quota_exceeded", "insufficient_credits") or "quota" in msg.lower() or "credits" in msg.lower():
        return OutOfCredits("elevenlabs", "ElevenLabs character quota used up")
    if r.status_code in (401, 403):
        if status == "missing_permissions":
            return NotConfigured("elevenlabs", f"ElevenLabs key lacks a permission: {msg}")
        return NotConfigured("elevenlabs", "ElevenLabs API key missing or invalid")
    if r.status_code == 429:
        return ServiceDown("elevenlabs", "ElevenLabs rate limit / concurrency limit (will retry)")
    return ServiceDown("elevenlabs", f"ElevenLabs error {r.status_code}: {msg[:160]}")


def synthesize(text: str, voice: dict, *, channel_id=None, video_id=None) -> tuple[bytes, list[Word], float]:
    """Returns (mp3 bytes, word timings, cost_usd)."""
    voice_id = voice.get("voice_id") or "iP95p4xoKVk53GoZ742B"
    body = {
        "text": text,
        "model_id": voice.get("model_id") or "eleven_multilingual_v2",
        "voice_settings": {
            "stability": voice.get("stability", 0.45),
            "similarity_boost": voice.get("similarity_boost", 0.8),
            "style": voice.get("style", 0.15),
            "use_speaker_boost": True,
            "speed": voice.get("speed", 1.0),
        },
    }
    try:
        r = httpx.post(f"{API}/v1/text-to-speech/{voice_id}/with-timestamps",
                       params={"output_format": "mp3_44100_128"}, json=body, headers=_headers(), timeout=300)
    except httpx.TransportError as e:
        raise ServiceDown("elevenlabs", f"Cannot reach ElevenLabs: {e}") from e
    if r.status_code >= 400:
        raise _fail(r)
    d = r.json()
    audio = base64.b64decode(d["audio_base64"])
    al = d.get("alignment") or d.get("normalized_alignment")
    words = words_from_alignment(al["characters"], al["character_start_times_seconds"],
                                 al["character_end_times_seconds"])
    cost = len(text) * USD_PER_CHAR
    spend.record("elevenlabs", cost, units=len(text), unit="chars", detail="voiceover", channel_id=channel_id,
                 video_id=video_id)
    set_status("elevenlabs", "ok", None)
    return audio, words, cost


def words_from_alignment(chars: list[str], starts: list[float], ends: list[float]) -> list[Word]:
    words: list[Word] = []
    cur, s, e = "", None, 0.0
    for ch, st, en in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append(Word(cur, s or 0.0, e))
            cur, s = "", None
            continue
        if s is None:
            s = st
        cur += ch
        e = en
    if cur:
        words.append(Word(cur, s or 0.0, e))
    return words


def subscription() -> dict:
    """Live credit balance for the dashboard."""
    try:
        r = httpx.get(f"{API}/v1/user/subscription", headers=_headers(), timeout=30)
    except httpx.TransportError as e:
        raise ServiceDown("elevenlabs", f"Cannot reach ElevenLabs: {e}") from e
    if r.status_code >= 400:
        raise _fail(r)
    return r.json()


_PUNCT = re.compile(r"^[\W_]+|[\W_]+$")


def norm(w: str) -> str:
    return _PUNCT.sub("", w.lower())
