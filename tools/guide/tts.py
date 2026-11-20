"""Narration for the guide: one edge-tts call per Urdu sentence, joined with exact silences, so every
Roman Urdu subtitle gets an exact start/end.

  python tools/guide/tts.py build     → <out>/narration.json + <out>/audio/<scene>.wav
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("GUIDE_OUT", "/tmp/claude-0/-home-user-overthought-studio/"
                                         "9a68d7c5-bc7f-54ea-9349-55c1fc7db717/scratchpad/guide"))
VOICE, RATE = "ur-PK-AsadNeural", "-15%"
SR = 24000
GAP_S, SCENE_TAIL_S = 0.7, 1.0


@dataclass
class Cue:
    start: float
    end: float
    roman: str


def cues_from_boundaries(bounds: list[tuple[float, float]], roman: list[str], offset: float) -> list[Cue]:
    if len(bounds) != len(roman):
        raise ValueError(f"{len(bounds)} spoken sentences but {len(roman)} subtitle lines")
    return [Cue(round(offset + s, 3), round(offset + e, 3), r) for (s, e), r in zip(bounds, roman)]


async def _speak(text: str, path: Path) -> None:
    import edge_tts
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    await edge_tts.Communicate(text, VOICE, rate=RATE, proxy=proxy).save(str(path))


def _pcm(text: str, cache: Path) -> bytes:
    """16-bit mono PCM at SR for one sentence (cached by voice+rate+text)."""
    key = hashlib.sha1(f"{VOICE}|{RATE}|{text}".encode()).hexdigest()[:16]
    raw = cache / f"{key}.pcm"
    if not raw.exists():
        mp3 = cache / f"{key}.mp3"
        os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")
        for attempt in range(4):
            try:
                asyncio.run(_speak(text, mp3))
                if mp3.stat().st_size > 0:
                    break
            except Exception:
                if attempt == 3:
                    raise
        pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp3), "-af",
                              "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                              "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                              "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
        raw.write_bytes(pcm)
    return raw.read_bytes()


def synthesize_scene(scene: dict, out_dir: Path) -> tuple[Path, list[Cue], float]:
    cache = out_dir / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    gap = b"\x00\x00" * int(SR * GAP_S)
    buf, bounds, t = bytearray(), [], 0.0
    for i, sentence in enumerate(scene["urdu"]):
        pcm = _pcm(sentence, cache)
        dur = len(pcm) / 2 / SR
        bounds.append((t, t + dur))
        buf += pcm
        t += dur
        if i < len(scene["urdu"]) - 1:
            buf += gap
            t += GAP_S
    buf += b"\x00\x00" * int(SR * SCENE_TAIL_S)
    duration = len(buf) / 2 / SR
    wav = out_dir / "audio" / f"{scene['id']}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes(bytes(buf))
    return wav, cues_from_boundaries(bounds, scene["roman"], 0.0), round(duration, 3)


def build_all(script_path: Path, out_dir: Path) -> Path:
    sys.path.insert(0, str(HERE))
    import check_script
    data = check_script.load(script_path)
    result = {}
    for ch in data["chapters"]:
        for sc in ch["scenes"]:
            wav, cues, dur = synthesize_scene(sc, out_dir)
            result[sc["id"]] = {"audio": str(wav), "duration": dur,
                                "cues": [[c.start, c.end, c.roman] for c in cues]}
            print(f"{sc['id']}: {dur:.1f}s", flush=True)
    path = out_dir / "narration.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return path


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        p = build_all(HERE / "script.yaml", OUT)
        total = sum(v["duration"] for v in json.loads(p.read_text()).values())
        print(f"total narration {total / 60:.1f} min → {p}")
