"""Demo data for the LOCAL demo copy (tools/demo/up.sh). Never point this at the live project.

  python tools/demo/seed_demo.py                 # seed (idempotent)
  python tools/demo/seed_demo.py red-bar on|off  # show / clear the red "why it stopped" bar
  python tools/demo/seed_demo.py heartbeat       # mark the demo worker as running right now
  python tools/demo/seed_demo.py render <dir>    # (internal) render the demo video file offline
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
for line in (HERE / "demo.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k] = v


def is_local(url: str) -> bool:
    from urllib.parse import urlparse
    return urlparse(url).hostname in ("127.0.0.1", "localhost")


if not is_local(os.environ.get("SUPABASE_URL", "")):     # clear() wipes events/jobs: never touch a real project
    sys.exit("seed_demo refuses to run against a non-local Supabase")
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "localhost,127.0.0.1"
sys.path.insert(0, str(ROOT / "worker"))

from studio import db, seed  # noqa: E402

DEMO = {"demo": True}
NOW = datetime.now(timezone.utc)
VIDEO_PATH, THUMB_PATH = "overthought/demo/final.mp4", "overthought/demo/thumb.jpg"


def iso(dt: datetime) -> str:
    return dt.isoformat()


# ------------------------------------------------------------------ the demo video file
def render(out: Path) -> None:
    """Runs the real pipeline with faked services (worker/tests/fakes.py) on the hand-written doorway script."""
    import json
    from _pytest.monkeypatch import MonkeyPatch
    sys.path.insert(0, str(ROOT / "worker" / "tests"))
    import fakes
    from studio import content, pipeline
    mp = MonkeyPatch()
    w = fakes.install(mp, out / "work")
    w.script_factory = lambda: content.Script.model_validate(
        json.loads((ROOT / "worker" / "fixtures" / "doorway_script.json").read_text()))
    ch = fakes.seed_channel(w)
    v = fakes.seed_video(w, ch)
    pipeline.produce(v["id"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "final.mp4").write_bytes(w.storage[f"videos/{ch['slug']}/{v['id']}/final.mp4"])
    (out / "thumb.jpg").write_bytes(w.storage[f"videos/{ch['slug']}/{v['id']}/thumb.jpg"])
    mp.undo()


def ensure_media(render_dir: Path) -> None:
    if not (render_dir / "final.mp4").exists():
        subprocess.run([sys.executable, __file__, "render", str(render_dir)], check=True)
    db.upload("videos", VIDEO_PATH, (render_dir / "final.mp4").read_bytes(), "video/mp4")
    db.upload("videos", THUMB_PATH, (render_dir / "thumb.jpg").read_bytes(), "image/jpeg")


# ------------------------------------------------------------------ rows
POSTED = [
    ("Why you rehearse arguments in the shower that will never happen", 6),
    ("The spotlight effect: nobody noticed your shirt as much as you think", 9),
    ("Why your brain replays that embarrassing thing from 2014 at 2 a.m., and the simple trick that finally makes it stop", 13),
    ("Why you check your phone 96 times a day without deciding to", 19),
    ("The Zeigarnik effect: why unfinished tasks live in your head rent-free", 26),
]


def _video(ch: dict, title: str, status: str, **extra) -> dict:
    row = {"channel_id": ch["id"], "title": title, "status": status, "experiment": {**DEMO, "hook_style": "you-callout"},
           "video_path": VIDEO_PATH, "thumb_path": THUMB_PATH, "duration_s": 74.2, "progress": 100,
           "caption": f"{title} #psychology", "hashtags": ["#psychology", "#brainfacts", "#overthinking"],
           "cost_usd": 0.84, "cost_breakdown": {"research": 0.21, "script": 0.18, "factcheck": 0.12, "images": 0.08,
                                                "voice": 0.25}}
    row.update(extra)
    return db.insert("videos", row)[0]


def _stats(video: dict, posted_at: datetime, seed_views: int) -> list[dict]:
    rows, n = [], 0
    t = posted_at + timedelta(hours=6)
    while t < NOW and n < 30:
        n += 1
        views = int(seed_views * (1 - 0.85 ** n))
        rows.append({"video_id": video["id"], "captured_at": iso(t), "views": views, "likes": views // 12,
                     "comments": views // 180, "shares": views // 95, "saves": views // 60,
                     "raw": DEMO})
        t += timedelta(hours=6)
    return rows


def clear() -> None:
    db.delete("videos", {"experiment->>demo": "true"})          # cascades stats, jobs, events tied to videos
    db.delete("events", {"id": ("gte", 0)})       # local demo DB only: start every run with a clean activity feed
    db.delete("jobs", {"id": ("gte", 0)})
    db.delete("reports", {"data->>demo": "true"})
    db.delete("spend", {"detail": "demo"})


def services_ok() -> None:
    vals = {
        "anthropic": dict(message="Estimated $18.40 left", balance=18.4, balance_unit="usd", balance_limit=25),
        "voice": dict(message=None, balance=12, balance_unit="voices"),
        "runpod": dict(message=None, balance=12.3, balance_unit="usd"),
        "tiktok": dict(message="1 account connected"),
        "storage": dict(message=None),
        "worker": dict(message="demo-worker v1.0.0"),
    }
    for name, v in vals.items():
        db.update("services", {"name": name}, {"status": "ok", "checked_at": iso(NOW), **v})


def set_red_bar(on: bool) -> None:
    if on:
        db.update("services", {"name": "runpod"}, {
            "status": "out_of_credits", "balance": 0, "checked_at": iso(NOW),
            "message": "RunPod balance is empty. Add funds at runpod.io → Billing. Work resumes automatically."})
    else:
        db.update("services", {"name": "runpod"}, {"status": "ok", "message": None, "balance": 12.3,
                                                   "checked_at": iso(NOW)})


def heartbeat() -> None:
    db.insert("worker_heartbeats", {"worker_id": "demo-worker", "version": "1.0.0", "host": "demo",
                                    "last_seen": iso(datetime.now(timezone.utc)), "info": {"cpus": 4}},
              upsert=True, on_conflict="worker_id")


def run(render_dir: Path) -> dict[str, int]:
    if not db.select("channels", {"slug": "overthought"}, single=True):
        seed.run()
    ensure_media(Path(render_dir))
    clear()
    ch = db.update("channels", {"slug": "overthought"}, {
        "status": "active", "posting_mode": "draft", "require_approval": True,
        "strategy": {"week_of": (NOW - timedelta(days=NOW.weekday())).date().isoformat(),
                     "pillar_weights": {"Why you do that": 0.6, "Spot the trick": 0.25, "Brain myths": 0.15},
                     "hook_weights": {"you-callout": 1.3, "question": 1.1, "myth-bust": 0.9, "number": 0.8},
                     "test": {"variable": "hook", "variant": "question"},
                     "notes": "'You' callouts held viewers 18% longer than numbers. This week tests question hooks."}})[0]

    ago = lambda **kw: iso(NOW - timedelta(**kw))  # noqa: E731
    import json
    script = json.loads((ROOT / "worker" / "fixtures" / "doorway_script.json").read_text())
    ready = _video(ch, "Why you forget why you walked into a room", "ready", approval="pending", created_at=ago(minutes=35),
                   script=script, script_version=1, caption=script.get("caption"), hashtags=script.get("hashtags") or [],
                   scorecard={"hook": 9, "curiosity_gap": 9, "viewer_question": 8, "emotional_connection": 8, "clarity": 9,
                              "pacing": 8, "accuracy_framing": 9, "loop": 8, "originality": 8, "overall": 8.6,
                              "biggest_risk": "The middle beat is slower than the hook.", "fixes": []},
                   factcheck={"claims": [{"claim": "Walking through a doorway makes people forget more than staying in one room.",
                                          "verdict": "supported", "evidence": "Radvansky et al. 2011, Notre Dame; replicated in "
                                          "virtual and real rooms.", "source_url": "https://doi.org/10.1080/17470218.2011.571267"}],
                              "citations_valid": True, "passes": True, "required_changes": [],
                              "summary": "All claims supported; the effect size is described honestly."})
    sched = _video(ch, "Why a full inbox makes you more tired than a long workday", "scheduled",
                   approval="approved", created_at=ago(hours=9), approved_at=iso(NOW - timedelta(hours=3)),
                   scheduled_for=iso((NOW + timedelta(days=1)).replace(hour=23, minute=30, second=0, microsecond=0)))
    stats = []
    for i, (title, days) in enumerate(POSTED):
        posted_at = NOW - timedelta(days=days, hours=2)
        v = _video(ch, title, "posted", approval="approved", posted_at=iso(posted_at),
                   created_at=iso(posted_at - timedelta(hours=20)),
                   publish_status={"status": "SEND_TO_USER_INBOX"})
        stats += _stats(v, posted_at, [42000, 18500, 96000, 12800, 30500][i])
    db.insert("video_stats", stats)
    failed = _video(ch, "Do we really use only 10% of our brain?", "failed", video_path=None, thumb_path=None,
                    created_at=ago(hours=2),
                    duration_s=None, progress=40, cost_usd=0.41,
                    error="Fact-check failed after 2 rewrites: the '10% of the brain' claim has no supporting study; "
                          "rewrite as a myth-bust.")
    voice = _video(ch, "Why you say 'you too' when the waiter says enjoy your meal", "voice", video_path=None,
                   thumb_path=None, created_at=ago(minutes=12), duration_s=None, progress=70, stage_detail="Recording the voiceover", cost_usd=0.52)
    _video(ch, "Why you can't tickle yourself", "rejected", approval="rejected", created_at=ago(days=2),
           rejection_note="Hook is too slow; the study is from 1998, find a newer one.")

    for job in [
        {"type": "produce_video", "status": "running", "payload": {**DEMO, "video_id": voice["id"]},
         "video_id": voice["id"], "channel_id": ch["id"], "locked_by": "demo-worker:heavy", "locked_at": iso(NOW)},
        {"type": "publish_video", "status": "queued", "payload": {**DEMO, "video_id": sched["id"]},
         "video_id": sched["id"], "channel_id": ch["id"], "run_after": sched["scheduled_for"]},
        {"type": "sync_stats", "status": "done", "payload": DEMO, "result": {"updated": 5},
         "finished_at": iso(NOW - timedelta(minutes=40))},
        {"type": "health_check", "status": "done", "payload": DEMO, "result": {"ok": 6},
         "finished_at": iso(NOW - timedelta(minutes=8))},
    ]:
        db.insert("jobs", job)        # rows have different keys: PostgREST bulk insert needs matching keys
    ev = [("success", "pipeline", f"Ready: {ready['title']} (74.2s, $0.84) — waiting for your approval", ready, 25),
          ("info", "pipeline", f"{voice['title']}: Recording the voiceover", voice, 6),
          ("error", "jobs", f"produce_video failed permanently: {failed['error'][:120]}", failed, 95),
          ("success", "publish", f"Sent to TikTok drafts: {POSTED[0][0]}", None, 60 * 24 * 6),
          ("info", "stats", "Stats synced for 5 videos", None, 40),
          ("success", "services", "runpod is now ok", None, 60 * 5),
          ("warn", "budget", "Daily spend is at 80% of the $15 budget", None, 60 * 20),
          ("info", "review", "Weekly review: pillar mix updated, testing question hooks", None, 60 * 24 * 3),
          ("info", "worker", "Worker demo-worker started (v1.0.0)", None, 60 * 26)]
    db.insert("events", [{"level": lvl, "scope": sc, "message": msg, "data": DEMO, "channel_id": ch["id"],
                          "video_id": v["id"] if v else None, "created_at": iso(NOW - timedelta(minutes=m))}
                         for lvl, sc, msg, v, m in ev])
    db.insert("reports", {"channel_id": ch["id"], "kind": "weekly", "data": DEMO,
                          "period_start": (NOW - timedelta(days=7)).date().isoformat(),
                          "period_end": NOW.date().isoformat(), "title": "Overthought — week in review",
                          "summary_md": "**Best video:** the 2 a.m. cringe replay (96k views, 61% watched to the end).\n\n"
                                        "**What worked:** 'you' callout hooks kept people 18% longer.\n\n"
                                        "**This week:** testing question hooks on half the videos.",
                          "changes": [{"what": "hook weights", "from": "even", "to": "you-callout 1.3"}]})
    db.insert("spend", [{"service": s, "amount_usd": a, "detail": "demo", "channel_id": ch["id"],
                         "created_at": iso(NOW - timedelta(days=d))}
                        for d in range(1, 15) for s, a in (("anthropic", 0.48), ("runpod", 0.08))])
    from studio import crypto
    for key in ("anthropic_api_key", "runpod_api_key"):   # fake keys so Settings looks set up
        fake = f"sk-demo-not-a-real-key-{key[:4]}"
        db.insert("secrets", {"key": key, "ciphertext": crypto.encrypt(fake), "hint": fake[-4:]},
                  upsert=True, on_conflict="key")
    from studio import settings
    settings.put("anthropic_credit", {"balance_usd": 25, "set_at": iso(NOW - timedelta(days=14))})
    services_ok()
    heartbeat()
    return {"videos": len(db.select("videos", {"experiment->>demo": "true"}, columns="id")),
            "video_stats": len(stats),
            "events": len(db.select("events", {"data->>demo": "true"}, columns="id")),
            "jobs": len(db.select("jobs", {"payload->>demo": "true"}, columns="id")),
            "reports": len(db.select("reports", {"data->>demo": "true"}, columns="id"))}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if cmd == "render":
        render(Path(sys.argv[2]))
    elif cmd == "red-bar":
        set_red_bar(sys.argv[2] == "on")
    elif cmd == "heartbeat":
        heartbeat()
    else:
        print(run(HERE / ".renders"))
