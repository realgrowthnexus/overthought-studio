"""Hand-written text layers (Kalam body + Caveat Brush keyword), soft blurred shadows, wobbly underline."""
from __future__ import annotations

import functools
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .. import config

RGB = tuple[int, int, int]


@functools.lru_cache(maxsize=64)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(config.FONTS / name), size)


def _measure(text: str, f: ImageFont.FreeTypeFont) -> float:
    return ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(text, font=f)


def wobble_underline(d: ImageDraw.ImageDraw, x: float, w: float, y: float, th: int, seed: int, color: RGB,
                     progress: float = 1.0) -> None:
    rnd = random.Random(seed)
    n = 16
    pts = [(x - 6 + (w + 12) * i / (n - 1), y + math.sin(i * 0.8 + seed) * th * 0.6 + rnd.uniform(-1.5, 1.5))
           for i in range(n)]
    k = max(2, int(n * max(0.0, min(1.0, progress))))
    d.line(pts[:k], fill=color + (235,), width=th, joint="curve")


def _wrap(parts: list[tuple[str, str]], fonts: dict, max_w: float) -> list[list[tuple[str, str]]]:
    """Split parts into words and wrap into lines (keeps kinds)."""
    words: list[tuple[str, str]] = []
    for t, k in parts:
        for i, wd in enumerate(t.split()):
            words.append((wd, k))
    lines: list[list[tuple[str, str]]] = [[]]
    cur = 0.0
    space = _measure(" ", fonts["ink"])
    for wd, k in words:
        w = _measure(wd, fonts[k])
        if lines[-1] and cur + space + w > max_w:
            lines.append([])
            cur = 0.0
        cur += (space if lines[-1] else 0) + w
        lines[-1].append((wd, k))
    return [ln for ln in lines if ln]


def text_layer(parts: list[tuple[str, str]], size: int, *, ink: RGB, key: RGB, body_font: str, key_font: str,
               max_w: int = 860, rot: float = -1.5, seed: int = 1, underline: float = 1.0,
               shadow: float = 0.85) -> Image.Image:
    """parts: [(text, 'ink'|'key')]. Returns RGBA image, centered lines, tilted, soft shadow."""
    fonts = {"ink": font(body_font, size), "key": font(key_font, int(size * 1.22))}
    cols = {"ink": ink, "key": key}
    # balanced wrapping: avoid a lonely last word
    space0 = _measure(" ", fonts["ink"])
    total = sum(_measure(w, fonts[k]) + space0 for t, k in parts for w in t.split())
    n_lines = max(1, math.ceil(total / max_w))
    lines = _wrap(parts, fonts, min(max_w, total / n_lines * 1.12) if n_lines > 1 else max_w)
    if len(lines) > n_lines:
        lines = _wrap(parts, fonts, max_w)
    lh = int(size * 1.32)
    space = _measure(" ", fonts["ink"])
    widths = [sum(_measure(w, fonts[k]) for w, k in ln) + space * (len(ln) - 1) for ln in lines]
    W = int(max(widths or [10])) + 120
    H = lh * len(lines) + int(size * 0.9)
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    for li, ln in enumerate(lines):
        x = (W - widths[li]) / 2
        base = int(size * 1.05) + li * lh
        for wd, k in ln:
            f = fonts[k]
            w = _measure(wd, f)
            d.text((x, base), wd, font=f, fill=cols[k] + (255,), anchor="ls")
            if k == "key" and underline > 0:
                wobble_underline(d, x, w, base + size * 0.2, max(4, size // 14), seed, key, underline)
            x += w + space
    L = L.rotate(rot, resample=Image.BICUBIC, expand=True)
    if shadow <= 0:
        return L
    sh = Image.new("RGBA", L.size, (0, 0, 0, 0))
    sh.putalpha(L.getchannel("A").point(lambda a: int(a * shadow)))
    sh = sh.filter(ImageFilter.GaussianBlur(max(4, size // 10)))
    out = Image.new("RGBA", (L.width + 8, L.height + 10), (0, 0, 0, 0))
    out.alpha_composite(sh, (4, 8))
    out.alpha_composite(L, (0, 0))
    return out


def caption_layer(words: list[str], active: int, size: int, *, ink: RGB, dim: RGB, body_font: str,
                  max_w: int = 860) -> Image.Image:
    """Word-by-word captions: the spoken word is bright and slightly larger, the rest dim."""
    f = font(body_font, size)
    fa = font(body_font, int(size * 1.08))
    space = _measure(" ", f)
    ws = [_measure(w, fa if i == active else f) for i, w in enumerate(words)]
    # wrap into up to 2 lines
    lines, cur, acc = [[]], 0.0, []
    for i, w in enumerate(ws):
        if lines[-1] and cur + space + w > max_w:
            lines.append([])
            cur = 0.0
        cur += (space if lines[-1] else 0) + w
        lines[-1].append(i)
    lh = int(size * 1.25)
    W = max_w + 40
    H = lh * len(lines) + int(size * 0.6)
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    for li, ln in enumerate(lines):
        tw = sum(ws[i] for i in ln) + space * (len(ln) - 1)
        x = (W - tw) / 2
        base = int(size * 1.0) + li * lh
        for i in ln:
            on = i == active
            d.text((x, base), words[i], font=fa if on else f, fill=(ink if on else dim) + (255,), anchor="ls")
            x += ws[i] + space
    sh = Image.new("RGBA", L.size, (0, 0, 0, 0))
    sh.putalpha(L.getchannel("A").point(lambda a: int(a * 0.9)))
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    out = Image.new("RGBA", L.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (2, 5))
    out.alpha_composite(L)
    return out


def margin_note(text: str, size: int, color: RGB, body_font: str, seed: int = 3) -> Image.Image:
    f = font(body_font, size)
    w = int(_measure(text, f))
    L = Image.new("RGBA", (w + 90, int(size * 1.6)), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    rnd = random.Random(seed)
    y = size * 0.75
    pts = [(6, y)] + [(6 + i * 9, y + rnd.uniform(-2, 2)) for i in range(1, 6)]
    d.line(pts, fill=color + (255,), width=3)
    d.line([(51, y), (39, y - size * 0.3)], fill=color + (255,), width=3)
    d.line([(51, y), (39, y + size * 0.3)], fill=color + (255,), width=3)
    d.text((66, size * 0.12), text, font=f, fill=color + (255,))
    return L


def bug(text: str, size: int, ink: RGB, accent: RGB, body_font: str) -> Image.Image:
    f = font(body_font, size)
    w = int(_measure(text, f))
    L = Image.new("RGBA", (w + 70, int(size * 1.5)), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    d.text((0, 0), text, font=f, fill=ink + (200,))
    rnd = random.Random(3)
    cx, cy = w + 26, size * 0.62
    pts = [(cx + math.cos(t * 0.7) * (8 + rnd.uniform(-3, 3)), cy + math.sin(t * 0.9) * (7 + rnd.uniform(-3, 3)))
           for t in range(30)]
    d.line(pts, fill=accent + (255,), width=3, joint="curve")
    return L
