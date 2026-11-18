"""Hand-drawn accent elements, drawn in code (never by the image model) so the figure never turns yellow.

Each accent is a list of polylines in a unit box (0..1). draw() renders them partially (stroke progress) with a
wobbly, slightly irregular hand-drawn line and a soft glow.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

Path = list[tuple[float, float]]


def _arc(cx, cy, r, a0, a1, n=24, rx=None, ry=None) -> Path:
    rx, ry = rx or r, ry or r
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / (n - 1)), cy + ry * math.sin(a0 + (a1 - a0) * i / (n - 1)))
            for i in range(n)]


def _paths(kind: str, seed: int) -> list[Path]:
    rnd = random.Random(seed)
    if kind == "question_mark":
        top = _arc(0.5, 0.32, 0.2, math.pi * 1.05, math.pi * 2.35, 30)
        stem = [top[-1], (0.52, 0.55), (0.5, 0.66)]
        dot = _arc(0.5, 0.86, 0.035, 0, math.pi * 2, 12)
        return [top + stem[1:], dot]
    if kind == "exclamation":
        return [[(0.5, 0.08), (0.52, 0.4), (0.5, 0.68)], _arc(0.5, 0.86, 0.04, 0, math.pi * 2, 12)]
    if kind == "lightbulb":
        bulb = _arc(0.5, 0.38, 0.27, math.pi * 0.75, math.pi * 2.25, 40)
        base = [(0.38, 0.68), (0.62, 0.68)], [(0.4, 0.76), (0.6, 0.76)], [(0.43, 0.84), (0.57, 0.84)]
        rays = [[(0.5 + 0.38 * math.cos(a), 0.38 + 0.38 * math.sin(a)), (0.5 + 0.48 * math.cos(a), 0.38 + 0.48 * math.sin(a))]
                for a in (math.pi * 1.1, math.pi * 1.3, math.pi * 1.5, math.pi * 1.7, math.pi * 1.9)]
        return [bulb, *base, *rays]
    if kind == "scribble_cloud":
        pts, a = [], 0.0
        for i in range(70):
            a += 0.55 + rnd.uniform(-0.15, 0.25)
            r = 0.22 + 0.16 * math.sin(i * 0.37) + rnd.uniform(-0.06, 0.06)
            pts.append((0.5 + r * math.cos(a), 0.5 + 0.8 * r * math.sin(a)))
        return [pts]
    if kind == "arrow":
        shaft = [(0.1, 0.75), (0.35, 0.55), (0.6, 0.42), (0.86, 0.3)]
        return [shaft, [(0.86, 0.3), (0.7, 0.28)], [(0.86, 0.3), (0.8, 0.45)]]
    if kind == "circle":
        return [_arc(0.5, 0.5, 0.45, -0.4, math.pi * 2 + 0.25, 44, rx=0.47, ry=0.4)]
    if kind == "heart":
        l = [(0.5, 0.85), (0.22, 0.58), (0.14, 0.38), (0.2, 0.22), (0.35, 0.18), (0.5, 0.32)]
        r = [(0.5, 0.32), (0.65, 0.18), (0.8, 0.22), (0.86, 0.38), (0.78, 0.58), (0.5, 0.85)]
        return [l + r[1:]]
    if kind == "clock":
        return [_arc(0.5, 0.5, 0.4, 0, math.pi * 2.05, 40), [(0.5, 0.5), (0.5, 0.24)], [(0.5, 0.5), (0.68, 0.6)]]
    if kind == "check":
        return [[(0.15, 0.55), (0.4, 0.8), (0.88, 0.2)]]
    if kind == "cross":
        return [[(0.2, 0.2), (0.8, 0.8)], [(0.8, 0.2), (0.2, 0.8)]]
    if kind == "number":
        return [_arc(0.5, 0.5, 0.45, -0.5, math.pi * 2 + 0.3, 40, rx=0.48, ry=0.42)]
    return []


def _wobble(path: Path, seed: int, amt: float) -> Path:
    rnd = random.Random(seed)
    out = []
    for i, (x, y) in enumerate(path):
        out.append((x + rnd.uniform(-amt, amt) + 0.004 * math.sin(i * 1.7 + seed),
                    y + rnd.uniform(-amt, amt) + 0.004 * math.cos(i * 1.3 + seed)))
    return out


def _densify(path: Path, step: float = 0.01) -> Path:
    out = [path[0]]
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / step))
        for i in range(1, n + 1):
            out.append((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
    return out


def render(kind: str, size: int, color: tuple[int, int, int], progress: float, *, seed: int = 1,
           label: str | None = None, label_font: ImageFont.FreeTypeFont | None = None) -> Image.Image:
    """Returns an RGBA image (size x size) of the accent drawn to `progress` (0..1)."""
    pad = int(size * 0.15)
    S = size + 2 * pad
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    paths = [_densify(_wobble(p, seed + i, 0.008)) for i, p in enumerate(_paths(kind, seed))]
    total = sum(len(p) for p in paths) or 1
    budget = int(total * max(0.0, min(1.0, progress)))
    width = max(4, size // 22)
    for p in paths:
        if budget <= 1:
            break
        seg = p[:budget]
        budget -= len(seg)
        pts = [(pad + x * size, pad + y * size) for x, y in seg]
        if len(pts) > 1:
            d.line(pts, fill=color + (255,), width=width, joint="curve")
            r = width // 2
            for x, y in (pts[0], pts[-1]):
                d.ellipse((x - r, y - r, x + r, y + r), fill=color + (255,))
    if kind == "number" and label and label_font and progress > 0.5:
        a = int(255 * min(1.0, (progress - 0.5) * 2))
        d.text((S / 2, S / 2), label, font=label_font, fill=color + (a,), anchor="mm")
    glow = im.filter(ImageFilter.GaussianBlur(width * 1.6))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gl = glow.copy()
    gl.putalpha(gl.getchannel("A").point(lambda v: int(v * 0.55)))
    out.alpha_composite(gl)
    out.alpha_composite(im)
    return out


def ease_out_back(t: float, s: float = 1.7) -> float:
    t = max(0.0, min(1.0, t)) - 1
    return t * t * ((s + 1) * t + s) + 1


def pop_scale(t: float, dur: float = 0.35) -> float:
    """0 → 1.0 with a slight overshoot."""
    if t <= 0:
        return 0.0
    return max(0.0, ease_out_back(t / dur))
