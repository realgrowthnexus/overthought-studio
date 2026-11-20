"""Operator CLI.

  python -m studio.cli seed                          # create the 5 channels + idea bank
  python -m studio.cli manual <channel_slug> <script.json>   # produce a video from a hand-written script
  python -m studio.cli produce <video_id> [stage]   # run/resume production for one video
  python -m studio.cli health                        # run the health/credit check once
  python -m studio.cli tick                          # run one scheduler tick
  python -m studio.cli smoke                         # check every paid service once; one JSON line, exit 1 on any failure
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

from . import content, db, llm, ops, pipeline, scheduler, seed, voice

_KEYISH = re.compile(r"(sk-[A-Za-z0-9_-]{6,}|sb_secret_[A-Za-z0-9_-]+|(?i:bearer)\s+[A-Za-z0-9._-]{8,})")


def _clean(text: str) -> str:
    return _KEYISH.sub("***", ops._scrub(text))[:300]


def _part(fn) -> dict:
    try:
        return {"ok": True, **(fn() or {})}
    except Exception as e:
        return {"ok": False, "error": _clean(f"{type(e).__name__}: {e}")}


def _anthropic() -> dict:
    llm.ping()
    card, usd = llm.structured(content.Scorecard, "You are a strict TikTok retention editor.",
                               "Score this 3-line script quickly.\n1. Why do you forget why you walked into a room?\n"
                               "2. Doorways reset your brain's 'event' (Radvansky, Notre Dame, 2011).\n"
                               "3. So next time, say the task out loud before you move.",
                               purpose="smoke", effort="low", max_tokens=4000)
    return {"overall": card.overall, "usd": round(usd, 4)}


def _runpod() -> dict:
    st = ops._health_runpod()
    if st in ("unconfigured", "out_of_credits"):
        raise RuntimeError(f"RunPod {st}")
    return {"status": st}


def _ffmpeg() -> dict:
    out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout
    return {"version": out.split("\n", 1)[0]}


def smoke() -> dict:
    """Every external dependency once, each isolated so one failure never hides another."""
    res = {"supabase": _part(lambda: {"channels": len(db.select("channels", columns="slug"))}),
           "anthropic": _part(_anthropic),
           "elevenlabs": _part(lambda: {"chars_left": (lambda s: int(s.get("character_limit") or 0)
                                                       - int(s.get("character_count") or 0))(voice.subscription())}),
           "runpod": _part(_runpod),
           "ffmpeg": _part(_ffmpeg)}
    res["usd"] = (res["anthropic"].get("usd") or 0) if res["anthropic"]["ok"] else 0
    return res


def manual(slug: str, path: str) -> str:
    ch = db.select("channels", {"slug": slug}, single=True)
    script = content.Script.model_validate(json.load(open(path)))
    fc = {"claims": [], "citations_valid": True, "passes": True, "required_changes": [],
          "summary": "Hand-written script supplied by the operator; not machine fact-checked."}
    v = db.insert("videos", {"channel_id": ch["id"], "title": script.title, "status": "queued",
                             "script": script.model_dump(), "research": {"notes": "manual script", "citations": []},
                             "factcheck": fc, "caption": script.caption, "hashtags": script.hashtags,
                             "experiment": {"hook_style": script.hook_style, "manual": True}})[0]
    pipeline.produce(v["id"], from_stage="visuals")
    return v["id"]


def run(argv: list[str]) -> int:
    cmd, *args = argv or ["help"]
    if cmd == "smoke":
        res = smoke()
        print(json.dumps(res))
        return 0 if all(v["ok"] for v in res.values() if isinstance(v, dict)) else 1
    if cmd == "seed":
        seed.run()
    elif cmd == "manual":
        print(manual(*args))
    elif cmd == "produce":
        pipeline.produce(args[0], args[1] if len(args) > 1 else None)
    elif cmd == "health":
        print(ops.health_check())
    elif cmd == "tick":
        scheduler.tick()
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
