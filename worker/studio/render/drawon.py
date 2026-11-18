"""'Lines drawing on' effect.

We compute, for every line pixel of a scene, the time at which a pen would reach it: a geodesic flood fill along
the strokes starting at the top-most point of each connected stroke group (head first, then body, then props).
The result is a 0..1 'order map'; at progress p we show pixels whose order <= p (with a soft leading edge).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def order_map(mask: np.ndarray, work: int = 384) -> np.ndarray:
    """mask: float 0..1 (H,W). Returns float order 0..1 (H,W); background = 1.0."""
    h, w = mask.shape
    # work at reduced resolution for speed, then upsample
    sy, sx = h / work, w / work
    small = np.asarray(ndimage.zoom(mask, (work / h, work / w), order=1)) > 0.2
    small = ndimage.binary_dilation(small, iterations=1)
    order = np.full(small.shape, -1, dtype=np.int32)
    labels, n = ndimage.label(small, structure=np.ones((3, 3)))
    if n == 0:
        return np.ones_like(mask, dtype=np.float32)
    # components ordered top-to-bottom, bigger first on ties
    comps = []
    for lab in range(1, n + 1):
        ys, xs = np.nonzero(labels == lab)
        if len(ys) < 6:
            continue
        comps.append((ys.min(), -len(ys), lab, ys, xs))
    comps.sort()
    t = 0
    struct = np.ones((3, 3), dtype=bool)
    for _, _, lab, ys, xs in comps:
        comp = labels == lab
        i = int(np.argmin(ys))
        front = np.zeros_like(comp)
        front[ys[i], xs[i]] = True
        visited = front.copy()
        while front.any():
            order[front] = t
            t += 1
            nxt = ndimage.binary_dilation(front, structure=struct) & comp & ~visited
            visited |= nxt
            front = nxt
    order_f = order.astype(np.float32)
    order_f[order < 0] = t
    order_f /= max(1, t)
    big = ndimage.zoom(order_f, (sy, sx), order=0)[:h, :w]
    if big.shape != mask.shape:
        pad = np.ones_like(mask, dtype=np.float32)
        pad[:big.shape[0], :big.shape[1]] = big
        big = pad
    return big.astype(np.float32)


def reveal(order: np.ndarray, progress: float, edge: float = 0.04) -> np.ndarray:
    """Alpha multiplier (0..1) for the line layer at a given progress."""
    if progress >= 1.0:
        return np.ones_like(order)
    if progress <= 0.0:
        return np.zeros_like(order)
    return np.clip((progress - order) / edge + 1.0, 0.0, 1.0)
