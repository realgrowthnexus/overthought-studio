"""Original ambient music bed, synthesized from scratch (no licensing issues).

Soft detuned pads over a slow 4-chord loop, gentle sub, warm low-pass and a whisper of vinyl noise.
Each channel gets its own key/progression/tempo from a seed so beds differ but stay consistent per channel.
"""
from __future__ import annotations

import wave

import numpy as np
from scipy.signal import butter, lfilter

SR = 44100
PROGRESSIONS = [
    [[0, 3, 7, 10], [-4, 0, 3, 7], [-9, -5, 0, 3], [-2, 2, 5, 9]],     # i7 – VI – III – VII (moody)
    [[0, 4, 7, 11], [5, 9, 12, 16], [-3, 0, 4, 7], [7, 11, 14, 17]],    # Imaj7 – IV – vi – V (warm)
    [[0, 3, 7, 10], [5, 8, 12, 15], [-2, 2, 5, 9], [3, 7, 10, 14]],     # i – iv – VII – III
]


def _pad(freq: float, n: int, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.12, 0.0, 0.11):
        f = freq * (2 ** (det / 12))
        ph = rng.uniform(0, 2 * np.pi)
        out += np.sin(2 * np.pi * f * t + ph) + 0.25 * np.sin(4 * np.pi * f * t + ph)
    return out / 3


def bed(seconds: float, seed: int = 1, bpm: float = 68) -> np.ndarray:
    rng = np.random.default_rng(seed)
    prog = PROGRESSIONS[seed % len(PROGRESSIONS)]
    root = 220 * 2 ** (((seed * 5) % 7 - 3) / 12)         # A3 ± a few semitones
    bar = 4 * 60 / bpm
    n_total = int(seconds * SR) + SR
    out = np.zeros(n_total)
    i = 0
    pos = 0
    while pos < n_total:
        chord = prog[i % len(prog)]
        n = min(int(bar * 2 * SR), n_total - pos)          # 2 bars per chord
        seg = np.zeros(n)
        for st in chord:
            seg += _pad(root * 2 ** (st / 12), n, rng)
        seg += 0.6 * np.sin(2 * np.pi * (root / 2) * 2 ** (chord[0] / 12) * np.arange(n) / SR)
        env = np.minimum(1, np.arange(n) / (SR * 1.2)) * np.minimum(1, (n - np.arange(n)) / (SR * 1.2))
        out[pos:pos + n] += seg * env
        pos += n
        i += 1
    b, a = butter(2, 1400 / (SR / 2), "low")
    out = lfilter(b, a, out)
    noise = lfilter(*butter(1, 3000 / (SR / 2), "low"), rng.normal(0, 1, n_total)) * 0.02
    out = out + noise
    out /= np.max(np.abs(out)) + 1e-9
    fade = int(SR * 1.5)
    out[:fade] *= np.linspace(0, 1, fade)
    out = out[:int(seconds * SR)]
    out[-fade:] *= np.linspace(1, 0, fade)
    return out.astype(np.float32)


def write_wav(path: str, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767 * 0.9).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())
