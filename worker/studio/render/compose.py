"""Timeline → frames → H.264 MP4 (1080x1920, 30 fps) with voice + ducked music bed.

Layout respects TikTok safe zones: no text in the top 190px (tabs), bottom 380px (caption/username) or the right
120px (buttons). Text is centred on x=500 instead of 540 so it clears the right-hand buttons.
"""
from __future__ import annotations

import math
import multiprocessing as mp
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .. import config
from ..images import figure_bbox, hex_rgb, line_mask
from . import accents, drawon, music, text

W, H, FPS = 1080, 1920, 30
CX = 500                       # visual centre for text (clear of right-side buttons)
SCENE = 900                    # scene square size
SCENE_X, SCENE_Y = CX - SCENE // 2, 470
HOOK_Y = 215                   # top text zone 215..455
CAP_Y = 1350                   # captions zone 1350..1460
SRC_Y = 1468                   # source note 1468..1520
BUG_XY = (60, 1488)            # corner tag sits left of the source line when no source
DRAW_ON = 0.85                 # seconds for a new scene to draw on
TEXT_IN = 0.22


@dataclass
class BeatT:
    start: float
    end: float
    onscreen: list[tuple[str, str]]
    scene_id: int
    accent: str
    accent_label: str | None
    flash: bool
    source: str | None
    kind: str


@dataclass
class Spec:
    beats: list[BeatT]
    scenes: dict[int, str]                    # scene id → raw image path (white on black)
    words: list[tuple[str, float, float]]
    duration: float
    voice_path: str
    style: dict
    music_seed: int = 1
    out_path: str = ""
    thumb_path: str = ""
    extras: dict = field(default_factory=dict)


# ---------------------------------------------------------------- precompute
class Plan:
    def __init__(self, spec: Spec):
        st = spec.style
        self.spec = spec
        self.bg = hex_rgb(st.get("bg", "#111111"))
        self.ink = hex_rgb(st.get("ink", "#F6F1E6"))
        self.acc = hex_rgb(st.get("accent", "#FFD60A"))
        self.dim = tuple(int(self.bg[i] + (self.ink[i] - self.bg[i]) * 0.5) for i in range(3))
        self.body_font = st.get("body_font", "Kalam-Bold.ttf")
        self.key_font = st.get("key_font", "CaveatBrush-Regular.ttf")
        self.base = self._background()
        self.scenes = {}
        for sid, path in spec.scenes.items():
            raw = _fit_content(Image.open(path).convert("RGB")).resize((SCENE, SCENE), Image.LANCZOS)
            m = line_mask(raw)
            rgba = np.zeros((SCENE, SCENE, 4), dtype=np.uint8)
            rgba[..., :3] = self.ink
            rgba[..., 3] = (m * 255).astype(np.uint8)
            bb = figure_bbox(raw)
            self.scenes[sid] = {"rgba": rgba, "order": drawon.order_map(m), "bbox": bb,
                                "img": Image.fromarray(rgba, "RGBA")}
        # scene runs: start time of each contiguous run of the same scene
        self.run_start: list[float] = []
        self.run_end: list[float] = []
        for i, b in enumerate(spec.beats):
            if i > 0 and spec.beats[i - 1].scene_id == b.scene_id:
                self.run_start.append(self.run_start[-1])
            else:
                self.run_start.append(b.start)
        for i in range(len(spec.beats)):
            j = i
            while j + 1 < len(spec.beats) and spec.beats[j + 1].scene_id == spec.beats[i].scene_id:
                j += 1
            self.run_end.append(spec.beats[j].end)
        self.text_layers = [text.text_layer(b.onscreen, 80 if len(" ".join(t for t, _ in b.onscreen)) < 26 else 70,
                                            ink=self.ink, key=self.acc, body_font=self.body_font,
                                            key_font=self.key_font, max_w=820, rot=[-1.6, 1.0, -1.1][i % 3], seed=i + 1)
                            for i, b in enumerate(spec.beats)]
        self.src_layers = [text.margin_note(b.source.lstrip("→-> ").strip(), 36, self.acc, self.body_font, seed=i) if b.source else None
                           for i, b in enumerate(spec.beats)]
        self.bug = text.bug(st.get("bug_text", "overthought"), 34, self.ink, self.acc, self.body_font)
        self.chunks = self._chunks()
        self._cap_cache: dict[tuple[int, int], Image.Image] = {}
        self.acc_font = text.font(self.key_font, 64)

    def _background(self) -> Image.Image:
        g = np.zeros((H, W, 3), dtype=np.float32)
        yy, xx = np.mgrid[0:H, 0:W]
        d = np.sqrt(((xx - CX) / (W * 0.62)) ** 2 + ((yy - (SCENE_Y + SCENE / 2)) / (H * 0.42)) ** 2)
        glow = np.clip(1 - d, 0, 1) ** 1.6
        bg = np.array(self.bg, dtype=np.float32)
        lift = np.array([min(255, c + 14) for c in self.bg], dtype=np.float32)
        g[:] = bg + (lift - bg) * glow[..., None]
        noise = np.random.default_rng(3).normal(0, 1.2, (H, W, 1))
        return Image.fromarray(np.clip(g + noise, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    def _chunks(self) -> list[tuple[int, int, float, float]]:
        """Group words into caption chunks of ≤4 words, breaking after punctuation."""
        words = self.spec.words
        out, i = [], 0
        while i < len(words):
            j = i
            chars = len(words[i][0])
            while (j < len(words) - 1 and j - i < 3 and chars + 1 + len(words[j + 1][0]) <= 21
                   and not words[j][0].endswith((".", ",", "?", "!", ":", ";", "—"))):
                j += 1
                chars += 1 + len(words[j][0])
            out.append((i, j, words[i][1], words[j][2]))
            i = j + 1
        return out

    def caption(self, t: float) -> Image.Image | None:
        for ci, (a, b, s, e) in enumerate(self.chunks):
            nxt = self.chunks[ci + 1][2] if ci + 1 < len(self.chunks) else e + 0.6
            if s - 0.05 <= t < max(e, nxt - 0.02):
                active = a
                for k in range(a, b + 1):
                    if self.spec.words[k][1] <= t + 0.03:
                        active = k
                key = (ci, active)
                if key not in self._cap_cache:
                    if len(self._cap_cache) > 64:
                        self._cap_cache.clear()
                    ws = [w for w, _, _ in self.spec.words[a:b + 1]]
                    self._cap_cache[key] = text.caption_layer(ws, active - a, 58, ink=self.ink, dim=self.dim,
                                                              body_font=self.body_font, max_w=800)
                return self._cap_cache[key]
        return None

    def beat_at(self, t: float) -> int:
        for i, b in enumerate(self.spec.beats):
            if t < b.end:
                return i
        return len(self.spec.beats) - 1


def _fit_content(img: Image.Image, margin: float = 0.14, max_zoom: float = 2.0) -> Image.Image:
    """Crop a square around the drawing so the figure fills the scene area (model output is often small)."""
    x0, y0, x1, y1 = figure_bbox(img)
    w, h = img.size
    side = max(x1 - x0, y1 - y0) * (1 + 2 * margin)
    side = max(side, w / max_zoom)
    side = min(side, w)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    l = max(0, min(w - side, cx - side / 2))
    t = max(0, min(h - side, cy - side / 2))
    return img.crop((int(l), int(t), int(l + side), int(t + side)))


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _scene_frame(p: Plan, sid: int, t_in: float, run_dur: float, instant: bool, alpha_mult: float = 1.0):
    sc = p.scenes[sid]
    prog = 1.0 if instant else t_in / DRAW_ON
    if prog >= 1.0:
        img = sc["img"]
    else:
        rgba = sc["rgba"].copy()
        rgba[..., 3] = (rgba[..., 3] * drawon.reveal(sc["order"], prog)).astype(np.uint8)
        img = Image.fromarray(rgba, "RGBA")
    z = 1.0 + 0.055 * _ease(t_in / max(1.0, run_dur))           # slow push-in
    bx0, by0, bx1, by1 = sc["bbox"]
    fx, fy = (bx0 + bx1) / 2, (by0 + by1) / 2                  # zoom toward the figure
    size = int(SCENE * z)
    im = img.resize((size, size), Image.BILINEAR)
    ox = int(SCENE_X - (fx * z - fx))
    oy = int(SCENE_Y - (fy * z - fy))
    if alpha_mult < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * alpha_mult))
        im.putalpha(a)
    return im, (ox, oy), z, (fx, fy)


def _accent_pos(p: Plan, sid: int, kind: str, z: float, focus: tuple[float, float]) -> tuple[int, int, int]:
    bx0, by0, bx1, by1 = p.scenes[sid]["bbox"]
    fw, fh = bx1 - bx0, by1 - by0
    size = int(max(150, min(260, fh * 0.42)))
    if kind == "circle":
        size = int(max(160, min(300, fw * 0.9)))
        cx, cy = (bx0 + bx1) / 2, by0 + fh * 0.12
    elif kind == "arrow":
        cx, cy = bx0 - size * 0.45, by0 + fh * 0.35
    elif kind in ("question_mark", "exclamation", "lightbulb", "scribble_cloud"):
        cx, cy = (bx0 + bx1) / 2 + fw * 0.25, by0 - size * 0.45
    else:
        cx, cy = bx1 + size * 0.35, by0 + size * 0.2
    fx, fy = focus
    sx = SCENE_X + (cx - fx) * z + fx
    sy = SCENE_Y + (cy - fy) * z + fy
    sx = max(60 + size / 2, min(940 - size / 2, sx))
    sy = max(HOOK_Y + 260 + size / 2, min(CAP_Y - size / 2, sy))
    return int(sx), int(sy), size


def render_frame(p: Plan, t: float) -> Image.Image:
    spec = p.spec
    c = p.base.copy()
    bi = p.beat_at(t)
    b = spec.beats[bi]
    rs, re_ = p.run_start[bi], p.run_end[bi]
    first_run = rs <= spec.beats[0].start + 1e-6
    # previous scene fading out during the first 0.25s of a new run
    if bi > 0 and t - rs < 0.25 and spec.beats[bi - 1].scene_id != b.scene_id:
        pb = bi - 1
        im, xy, _, _ = _scene_frame(p, spec.beats[pb].scene_id, t - p.run_start[pb], p.run_end[pb] - p.run_start[pb],
                                    True, alpha_mult=1 - (t - rs) / 0.25)
        _paste(c, im, xy)
    im, xy, z, focus = _scene_frame(p, b.scene_id, t - rs, re_ - rs, instant=first_run)
    _paste(c, im, xy)
    # accent pop
    if b.accent and b.accent != "none":
        ta = t - b.start - (0.05 if bi == 0 else 0.2)
        if ta > 0:
            ax, ay, size = _accent_pos(p, b.scene_id, b.accent, z, focus)
            prog = min(1.0, ta / 0.45)
            a_img = accents.render(b.accent, size, p.acc, prog, seed=bi + 7, label=b.accent_label, label_font=p.acc_font)
            sc = accents.pop_scale(ta, 0.38) if ta < 0.6 else 1.0 + 0.012 * math.sin(ta * 3.2)
            if sc > 0.02:
                s = max(2, int(a_img.width * sc))
                a_img = a_img.resize((s, s), Image.BILINEAR)
                _paste(c, a_img, (ax - s // 2, ay - s // 2))
    # on-screen text (top)
    tl = p.text_layers[bi]
    k = 1.0 if (bi == 0 and t < 0.6) else _ease((t - b.start) / TEXT_IN)
    if k > 0:
        layer = tl if k >= 1 else _fade(tl, k)
        _paste(c, layer, (CX - tl.width // 2, HOOK_Y + int((1 - k) * 18) + max(0, (230 - tl.height) // 2)))
    # captions
    cap = p.caption(t)
    if cap is not None:
        _paste(c, cap, (CX - cap.width // 2, CAP_Y))
    # source note or corner tag
    src = p.src_layers[bi]
    if src is not None:
        ks = _ease((t - b.start - 0.3) / 0.3)
        if ks > 0:
            _paste(c, _fade(src, ks), (CX - src.width // 2, SRC_Y))
    else:
        _paste(c, p.bug, BUG_XY)
    # payoff flash
    if b.flash and 0 <= t - b.start < 0.28:
        x = (t - b.start) / 0.28
        a = int(46 * math.sin(math.pi * x))
        c.alpha_composite(Image.new("RGBA", (W, H), (*[min(255, (v + 255) // 2) for v in p.acc], a)))
    return c


def _paste(c: Image.Image, im: Image.Image, xy: tuple[int, int]) -> None:
    x, y = xy
    if x >= 0 and y >= 0 and x + im.width <= W and y + im.height <= H:
        c.alpha_composite(im, (x, y))
        return
    # clip
    l, t_ = max(0, -x), max(0, -y)
    r, b = min(im.width, W - x), min(im.height, H - y)
    if r > l and b > t_:
        c.alpha_composite(im.crop((l, t_, r, b)), (max(0, x), max(0, y)))


def _fade(im: Image.Image, k: float) -> Image.Image:
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lambda v: int(v * k)))
    return out


# ---------------------------------------------------------------- encode
_PLAN: Plan | None = None
_FRAME0: np.ndarray | None = None


def _render_segment(args: tuple[int, int, str]) -> str:
    a, b, path = args
    p = _PLAN
    assert p is not None
    total = int(round(p.spec.duration * FPS))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-g", str(FPS * 2), path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin
    loop_n = int(0.4 * FPS)
    for f in range(a, b):
        t = f / FPS
        fr = np.asarray(render_frame(p, t).convert("RGB"))
        if f >= total - loop_n and _FRAME0 is not None:                 # seamless loop: blend into frame 0
            k = (f - (total - loop_n)) / loop_n
            k = k * k * (3 - 2 * k)
            fr = (fr * (1 - k) + _FRAME0 * k).astype(np.uint8)
        proc.stdin.write(fr.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg segment encode failed")
    return path


def _run_segments(fn, jobs: list, procs: int) -> list:
    """Render segments in forked workers. Unlike multiprocessing.Pool, a worker killed by the OOM killer raises
    BrokenProcessPool at once instead of hanging the render forever."""
    if procs <= 1:
        return [fn(j) for j in jobs]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=procs, mp_context=mp.get_context("fork")) as pool:
        return list(pool.map(fn, jobs))


def render_video(spec: Spec, procs: int | None = None) -> dict:
    global _PLAN, _FRAME0
    _PLAN = Plan(spec)
    first = render_frame(_PLAN, 0.0).convert("RGB")
    _FRAME0 = np.asarray(first)
    if spec.thumb_path:
        first.save(spec.thumb_path, quality=92)
    total = int(round(spec.duration * FPS))
    procs = max(1, procs or config.RENDER_PROCS)
    tmp = Path(tempfile.mkdtemp(prefix="render_", dir=config.WORK))
    try:
        bounds = np.linspace(0, total, procs + 1).astype(int)
        jobs = [(int(bounds[i]), int(bounds[i + 1]), str(tmp / f"seg{i:02d}.mp4")) for i in range(procs)
                if bounds[i + 1] > bounds[i]]
        segs = _run_segments(_render_segment, jobs, procs)
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        silent = tmp / "video.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", str(silent)], check=True)
        bed = tmp / "bed.wav"
        music.write_wav(str(bed), music.bed(spec.duration + 0.5, seed=spec.music_seed))
        vol = float(spec.style.get("music_volume", 0.16))
        filt = (f"[2:a]volume={vol}[m];[1:a]apad=whole_dur={spec.duration:.3f},asplit=2[v1][v2];"
                f"[m][v2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md];"
                f"[v1][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-13:TP=-1.5:LRA=11[a]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", spec.voice_path, "-i", str(bed),
                        "-filter_complex", filt, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-ar", "44100", "-t", f"{spec.duration:.3f}", "-movflags", "+faststart",
                        spec.out_path], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        _PLAN = None
    return probe(spec.out_path)


def probe(path: str) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_name,width,height,r_frame_rate,pix_fmt:format=duration,size",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    import json
    d = json.loads(out)
    v = next(s for s in d["streams"] if s.get("width"))
    a = next((s for s in d["streams"] if not s.get("width")), {})
    return {"duration": float(d["format"]["duration"]), "size": int(d["format"]["size"]), "width": v["width"],
            "height": v["height"], "fps": v["r_frame_rate"], "vcodec": v["codec_name"], "pix_fmt": v.get("pix_fmt"),
            "acodec": a.get("codec_name")}


def audio_duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())
