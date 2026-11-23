"""Free voiceover: Kokoro-82M (Apache-2.0) runs on the VPS CPU. No API, no key, no bill, no quota.

The model export we use ("ONNX-timestamped") also returns how many audio frames each phoneme takes, so every word
gets an exact start/end for the synced captions. Each word is phonemized on its own, which tells us exactly which
tokens belong to which word; sentences are synthesized one at a time (the model takes ≤510 tokens).

Voices: one Kokoro voice name ("af_heart") or two blended ("am_michael+am_fenrir" = average of both styles).
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import logging

import numpy as np

from .services import NotConfigured, set_status

SR = 24000
logging.getLogger("phonemizer").setLevel(logging.ERROR)   # "words count mismatch" is normal for numbers
MODEL_DIR = Path(os.environ.get("STUDIO_KOKORO_DIR", "/opt/kokoro"))
MODEL = MODEL_DIR / "kokoro-v1.0-timestamped.onnx"
VOICES = MODEL_DIR / "voices-v1.0.bin"
MAX_TOKENS = 500                 # model limit is 510 incl. padding
SENTENCE_PAUSE = 0.22
CLAUSE_PAUSE = 0.08
DEFAULT_VOICE = "am_michael+am_fenrir"

# The voices offered in the dashboard (all US/UK English, picked by ear for narration).
CATALOG = {
    "am_michael+am_fenrir": "Male · deep, warm",
    "am_fenrir": "Male · deep",
    "am_michael": "Male · clear",
    "am_onyx": "Male · low, calm",
    "am_puck": "Male · energetic",
    "bm_george": "Male · British storyteller",
    "af_heart": "Female · warm",
    "af_bella": "Female · confident",
    "af_kore": "Female · calm, deep",
    "af_aoede": "Female · soft",
    "bf_emma": "Female · British",
    "af_heart+af_bella": "Female · rich blend",
}


@dataclass
class Word:
    text: str
    start: float
    end: float


class _Engine:
    def __init__(self) -> None:
        import onnxruntime as rt
        from kokoro_onnx.session import embedded_vocab
        from kokoro_onnx.tokenizer import Tokenizer

        opts = rt.SessionOptions()
        opts.intra_op_num_threads = int(os.environ.get("STUDIO_TTS_THREADS", "3"))
        self.sess = rt.InferenceSession(str(MODEL), sess_options=opts, providers=["CPUExecutionProvider"])
        outs = {o.name for o in self.sess.get_outputs()}
        if "durations" not in outs:
            raise NotConfigured("voice", "The voice model has no word timings (wrong model file) — rebuild the worker")
        self.voices = np.load(str(VOICES))
        self.tok = Tokenizer(vocab=embedded_vocab(self.sess) or None)
        self.lock = threading.Lock()      # one synthesis at a time keeps CPU use predictable next to the renders

    def style(self, name: str) -> np.ndarray:
        parts = [p.strip() for p in (name or DEFAULT_VOICE).split("+") if p.strip()]
        missing = [p for p in parts if p not in self.voices.files]
        if missing or not parts:
            raise ValueError(f"Unknown Kokoro voice: {', '.join(missing) or name!r}")
        return np.mean([self.voices[p] for p in parts], axis=0).astype(np.float32)

    def run(self, ids: list[int], style: np.ndarray, speed: float) -> tuple[np.ndarray, np.ndarray]:
        ref = style[min(len(ids), len(style)) - 1]
        wav, dur = self.sess.run(None, {"input_ids": np.array([[0, *ids, 0]], dtype=np.int64),
                                        "style": ref.astype(np.float32), "speed": np.array([speed], np.float32)})
        return np.asarray(wav, np.float32).ravel(), np.asarray(dur).ravel().astype(np.float64)


_engine: _Engine | None = None
_engine_lock = threading.Lock()


def engine() -> _Engine:
    global _engine
    with _engine_lock:
        if _engine is None:
            if not (MODEL.exists() and VOICES.exists()):
                raise NotConfigured("voice", f"Voice model files are missing in {MODEL_DIR} — rebuild the worker image")
            _engine = _Engine()
        return _engine


_SENT = re.compile(r"(?<=[.!?…])[\"')\]]*\s+")
_CLAUSE = re.compile(r"(?<=[,;:—–])\s+")


def _chunks(text: str) -> list[tuple[str, float]]:
    """Sentences (pause after each); long sentences are split at commas/semicolons."""
    out: list[tuple[str, float]] = []
    for s in [x.strip() for x in _SENT.split(re.sub(r"\s+", " ", text.strip())) if x.strip()]:
        if len(s) <= 300:
            out.append((s, SENTENCE_PAUSE))
            continue
        parts = [p for p in _CLAUSE.split(s) if p.strip()]
        for i, p in enumerate(parts):
            out.append((p, SENTENCE_PAUSE if i == len(parts) - 1 else CLAUSE_PAUSE))
    return out


def _tokens(eng: _Engine, words: list[str], lang: str) -> tuple[list[int], list[tuple[int, int]]]:
    space = eng.tok.tokenize(" ")
    ids: list[int] = []
    spans: list[tuple[int, int]] = []
    for i, w in enumerate(words):
        ph = eng.tok.phonemize(w, lang).strip()
        if i and ph:
            ids += space
        a = len(ids)
        ids += eng.tok.tokenize(ph, limit=None)
        spans.append((a, len(ids)))
    return ids, spans


def render_speech(text: str, voice_name: str, *, speed: float = 1.0, lang: str | None = None
                  ) -> tuple[np.ndarray, list[Word]]:
    """Float32 mono audio at 24 kHz + word timings (seconds from the start)."""
    eng = engine()
    style = eng.style(voice_name)
    lang = lang or ("en-gb" if (voice_name or "").startswith("b") else "en-us")
    audio: list[np.ndarray] = [np.zeros(int(SR * 0.12), np.float32)]      # a breath before the first word
    t = len(audio[0]) / SR
    words: list[Word] = []
    with eng.lock:
        for chunk, pause in _chunks(text):
            ws = chunk.split()
            pieces = [ws]
            ids, spans = _tokens(eng, ws, lang)
            if len(ids) > MAX_TOKENS:                                  # very long clause: split by word count
                n = max(1, len(ws) * MAX_TOKENS // (len(ids) + 1))
                pieces = [ws[i:i + n] for i in range(0, len(ws), n)]
            for piece in pieces:
                ids, spans = _tokens(eng, piece, lang) if len(pieces) > 1 else (ids, spans)
                if not ids:
                    continue
                wav, dur = eng.run(ids, style, speed)
                edges = np.concatenate([[0.0], np.cumsum(dur)]) * (len(wav) / max(1.0, dur.sum())) / SR
                for w, (a, b) in zip(piece, spans):                    # token k sits at index k+1 (leading pad)
                    s = t + edges[a + 1]
                    e = t + edges[b + 1] if b > a else s
                    words.append(Word(w, round(float(s), 3), round(float(max(s, e)), 3)))
                audio.append(wav)
                t += len(wav) / SR
            gap = np.zeros(int(SR * pause), np.float32)
            audio.append(gap)
            t += len(gap) / SR
    out = np.concatenate(audio)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out * (0.89 / peak)).astype(np.float32), words               # peak ≈ -1 dBFS


def to_mp3(samples: np.ndarray) -> bytes:
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0",
                        "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "96k", "-f", "mp3", "pipe:1"],
                       input=samples.astype("<f4").tobytes(), capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg could not encode the voiceover: " + p.stderr.decode()[-300:])
    return p.stdout


def voice_name(cfg: dict | None) -> str:
    cfg = cfg or {}
    name = cfg.get("voice") if cfg.get("provider") == "kokoro" else None
    return name or DEFAULT_VOICE


def synthesize(text: str, voice: dict, *, channel_id=None, video_id=None) -> tuple[bytes, list[Word], float]:
    """Returns (mp3 bytes, word timings, cost_usd). Cost is always 0 — it runs on our own CPU."""
    samples, words = render_speech(text, voice_name(voice), speed=float((voice or {}).get("speed") or 1.0))
    if not words:
        raise RuntimeError("The voiceover came out empty")
    mp3 = to_mp3(samples)
    set_status("voice", "ok", None)
    return mp3, words, 0.0


def health() -> dict:
    """Cheap health check (every 10 min): the model files load. No synthesis."""
    eng = engine()
    return {"voices": len(eng.voices.files)}


def check() -> dict:
    """Smoke test: the model loads and speaks one short line."""
    samples, words = render_speech("Ready when you are.", DEFAULT_VOICE)
    return {"seconds": round(len(samples) / SR, 2), "words": len(words)}


_PUNCT = re.compile(r"^[\W_]+|[\W_]+$")


def norm(w: str) -> str:
    return _PUNCT.sub("", w.lower())
