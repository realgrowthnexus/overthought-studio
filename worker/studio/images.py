"""Scene generation on RunPod (Flux dev) + palette mapping.

Images come back as white line art on black (1024x1024). We map luminance onto the channel palette in code
(bg → ink), so every channel gets its own look from the same model and no black seams appear.
Accents are never generated — they are drawn in code (render/accents.py).
"""
from __future__ import annotations

import io
import time

import httpx
import numpy as np
from PIL import Image

from . import secrets, spend
from .services import NotConfigured, OutOfCredits, ServiceDown, set_status

ENDPOINT = "https://api.runpod.ai/v2/black-forest-labs-flux-1-dev/run"       # async: we always hold the job id
STATUS = "https://api.runpod.ai/v2/black-forest-labs-flux-1-dev/status/"
CANCEL = "https://api.runpod.ai/v2/black-forest-labs-flux-1-dev/cancel/"
DEFAULT_FIGURE = ("classic stick figure made of single thin white lines: circle head, one straight line body, "
                  "two line arms, two line legs, on pure black background, flat minimal hand-drawn vector, "
                  "monochrome white lines only, no shading, no text, no letters, no numbers, no logos, no signature, no watermark, ")
COST_FALLBACK = 0.012


def _headers() -> dict:
    key = secrets.get("runpod_api_key")
    # In the dev container the proxy injects the key; on the VPS the key comes from Settings/env.
    return {"Authorization": f"Bearer {key or 'proxy-injected'}", "Content-Type": "application/json"}


def _fail(r: httpx.Response) -> Exception:
    body = r.text[:300].lower()
    if r.status_code in (401, 403):
        if not secrets.get("runpod_api_key"):
            return NotConfigured("runpod", "No RunPod API key saved")
        return NotConfigured("runpod", "RunPod API key rejected")
    if r.status_code == 402 or "insufficient" in body or "balance" in body:
        return OutOfCredits("runpod", "RunPod balance is empty")
    return ServiceDown("runpod", f"RunPod error {r.status_code}")


WAIT_S = 300


def _ok(r: httpx.Response) -> httpx.Response:
    if r.status_code >= 400:
        raise _fail(r)
    return r


def generate(description: str, *, seed: int = 7, figure_prompt: str | None = None, channel_id=None,
             video_id=None) -> tuple[Image.Image, float]:
    with spend.runpod_slot():                 # hard monthly cap (Settings) — raises BudgetReached
        return _generate(description, seed=seed, figure_prompt=figure_prompt, channel_id=channel_id, video_id=video_id)


def _generate(description: str, *, seed: int, figure_prompt: str | None, channel_id, video_id
              ) -> tuple[Image.Image, float]:
    prompt = (figure_prompt or DEFAULT_FIGURE) + description
    body = {"input": {"prompt": prompt, "num_inference_steps": 28, "guidance": 3.5, "seed": int(seed),
                      "width": 1024, "height": 1024}}
    with httpx.Client(timeout=60) as c:
        try:
            d = _ok(c.post(ENDPOINT, json=body, headers=_headers())).json()
            job = d.get("id")
            t0 = time.time()
            while d.get("status") in ("IN_QUEUE", "IN_PROGRESS") and time.time() - t0 < WAIT_S:
                time.sleep(2)
                d = _ok(c.get(STATUS + job, headers=_headers())).json()
            if d.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
                try:   # stop paying for a job we no longer wait for
                    c.post(CANCEL + job, headers=_headers())
                except httpx.HTTPError:
                    pass
                raise RuntimeError("RunPod image took longer than 5 minutes (cold start?) — will retry")
            if d.get("status") != "COMPLETED":
                raise RuntimeError(f"RunPod image job ended with status {d.get('status')}: {str(d.get('error'))[:200]}")
            out = d["output"]
            url = out.get("result") or out.get("image_url") or (out.get("images") or [None])[0]
            r = c.get(url)
            if r.status_code >= 400:
                raise ServiceDown("runpod", f"Could not download the image ({r.status_code})")
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
        except httpx.TransportError as e:
            raise ServiceDown("runpod", f"Cannot reach RunPod: {e}") from e
    cost = float(out.get("cost") or COST_FALLBACK)
    spend.record("runpod", cost, units=1, unit="image", detail="flux scene", channel_id=channel_id, video_id=video_id)
    set_status("runpod", "ok", None)
    return img, cost


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _norm_lum(img: Image.Image) -> np.ndarray:
    """Luminance normalised so the image's own background → 0 and its lines → 1.
    Flux sometimes returns dark-grey instead of black backgrounds; this removes the visible square."""
    a = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
    bg = float(np.percentile(a, 50))                      # most pixels are background
    hi = float(np.percentile(a, 99.7))
    span = max(0.2, hi - bg)
    return np.clip((a - bg - 0.06) / (span - 0.06), 0, 1)


def to_palette(img: Image.Image, bg: str, ink: str, gamma: float = 1.0) -> Image.Image:
    """Map luminance onto bg→ink. Also cleans faint grey noise so backgrounds are perfectly flat."""
    a = _norm_lum(img) ** gamma
    b = np.array(hex_rgb(bg), dtype=np.float32)
    k = np.array(hex_rgb(ink), dtype=np.float32)
    out = b[None, None, :] + (k - b)[None, None, :] * a[..., None]
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGB")


def line_mask(img: Image.Image) -> np.ndarray:
    """Float mask 0..1 of the drawn lines (for draw-on animation)."""
    return _norm_lum(img)


def figure_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    m = line_mask(img) > 0.35
    ys, xs = np.nonzero(m)
    if len(xs) < 50:
        w, h = img.size
        return (w // 4, h // 4, 3 * w // 4, 3 * h // 4)
    return (int(np.percentile(xs, 1)), int(np.percentile(ys, 1)), int(np.percentile(xs, 99)), int(np.percentile(ys, 99)))
