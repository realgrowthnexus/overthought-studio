"""Operator CLI.

  python -m studio.cli seed                          # create the 5 channels + idea bank
  python -m studio.cli manual <channel_slug> <script.json>   # produce a video from a hand-written script
  python -m studio.cli produce <video_id> [stage]   # run/resume production for one video
  python -m studio.cli health                        # run the health/credit check once
  python -m studio.cli tick                          # run one scheduler tick
  python -m studio.cli smoke                         # check every paid service once; one JSON line, exit 1 on any failure
  python -m studio.cli claude-token < token          # save the Claude sign-in token (used by infra/connect-claude.sh)
  python -m studio.cli claude-status                 # one line: Claude sign-in + limits (used by infra/doctor.sh)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

from .services import ServiceProblem
from . import claude_cli, content, crypto, db, llm, ops, pipeline, scheduler, secrets, seed, voice

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


_OAT = re.compile(r"sk-ant-oat\d\d-[A-Za-z0-9_-]{30,}")


def claude_token(raw: str) -> int:
    """Store the Claude subscription token encrypted, like the dashboard stores API keys. Never prints it."""
    m = _OAT.search(re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", raw))
    if not m:
        print("That doesn't look like a Claude sign-in token (sk-ant-oat…). Nothing was saved.")
        return 1
    tok = m.group(0)
    try:                                             # one tiny real call proves the sign-in works before saving it
        claude_cli.run("Reply with the word ok.", system="Reply with one word.", schema=None, tools=[],
                       model="sonnet", timeout=180, with_token=tok)
    except ServiceProblem as p:
        if p.status == "unconfigured":
            print("Claude did NOT accept this sign-in (the token was rejected or cut off). Nothing was saved. "
                  "Run connect-claude.sh again.")
            return 1
    except Exception as e:
        print(f"Could not test the sign-in right now ({_clean(str(e))}); saving it anyway.")
    db.insert("secrets", {"key": "claude_oauth_token", "ciphertext": crypto.encrypt(tok), "hint": tok[-4:]},
              upsert=True, on_conflict="key")
    secrets.clear_cache()
    row = db.select("services", {"name": "anthropic"}, single=True) or {}
    if (row.get("details") or {}).get("auth_rejected"):
        db.update("services", {"name": "anthropic"}, {"details": {**row["details"], "auth_rejected": False}})
    try:
        ops.health_check()
    except Exception as e:
        print(f"Saved, but the health check could not run yet: {_clean(str(e))}")
    print("Claude connected ✓ (sign-in saved, encrypted)")
    return 0


def claude_status() -> str:
    if llm.backend() == "api":
        return "using an Anthropic API key (Claude sign-in not in use)"
    if not claude_cli.auth_ok():
        return "NOT signed in — run: sudo bash /opt/overthought-studio/src/infra/connect-claude.sh"
    d = (db.select("services", {"name": "anthropic"}, single=True) or {}).get("details") or {}
    parts = ["connected (Claude subscription)"]
    for key, label in (("five_hour", "5-hour"), ("seven_day", "weekly")):
        w = d.get(key) or {}
        if w.get("pct") is not None:
            parts.append(f"{label} {int(w['pct'])}%")
    if d.get("limited"):
        parts.append(f"limit reached, resumes {d.get('resume_at')}")
    if d.get("pacing"):
        parts.append("pacing on (evening videos paused)")
    return " · ".join(parts)


def run(argv: list[str]) -> int:
    cmd, *args = argv or ["help"]
    if cmd == "smoke":
        res = smoke()
        print(json.dumps(res))
        return 0 if all(v["ok"] for v in res.values() if isinstance(v, dict)) else 1
    if cmd == "claude-token":
        return claude_token(sys.stdin.read())
    if cmd == "claude-status":
        print(claude_status())
        return 0
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
