"""Operator CLI.

  python -m studio.cli seed                          # create the 5 channels + idea bank
  python -m studio.cli manual <channel_slug> <script.json>   # produce a video from a hand-written script
  python -m studio.cli produce <video_id> [stage]   # run/resume production for one video
  python -m studio.cli health                        # run the health/credit check once
  python -m studio.cli tick                          # run one scheduler tick
"""
from __future__ import annotations

import json
import sys

from . import content, db, ops, pipeline, scheduler, seed


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


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
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
