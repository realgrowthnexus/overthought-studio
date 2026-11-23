"""SubRip subtitles from cues."""
from __future__ import annotations


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues) -> str:
    return "".join(f"{i}\n{_ts(c.start)} --> {_ts(c.end)}\n{c.roman}\n\n" for i, c in enumerate(cues, 1))
