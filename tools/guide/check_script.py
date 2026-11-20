"""Loads tools/guide/script.yaml and rejects anything that would break subtitle timing or readability."""
from __future__ import annotations

from pathlib import Path

import yaml

END_MARKS = ("۔", "؟", "!")
MAX_ROMAN = 84          # two subtitle lines of ~42 characters


def load(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for ch in data["chapters"]:
        for sc in ch["scenes"]:
            sid, roman, urdu = sc["id"], sc["roman"], sc["urdu"]
            if len(roman) != len(urdu):
                raise ValueError(f"{sid}: {len(roman)} Roman lines vs {len(urdu)} Urdu sentences")
            for u in urdu:
                if not u.strip().endswith(END_MARKS):
                    raise ValueError(f"{sid}: Urdu sentence lacks an end mark: {u[:30]}")
                if any(m in u.strip()[:-1] for m in END_MARKS):
                    raise ValueError(f"{sid}: one Urdu line holds two sentences: {u[:30]}")
            for r in roman:
                if len(r) > MAX_ROMAN:
                    raise ValueError(f"{sid}: Roman line over {MAX_ROMAN} chars: {r[:30]}")
    return data
