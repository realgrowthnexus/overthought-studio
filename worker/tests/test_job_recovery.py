"""Failed videos give their idea back (A5); orphaned videos are swept and startup reset honours attempts (A2)."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import config, main, ops
from studio.services import PermanentError

from fakes import install, seed_channel

T = datetime.now(timezone.utc)


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    return w


def _video(w, status="queued", idea_id=None, minutes_ago=0):
    return w.insert("videos", {"channel_id": w.ch["id"], "title": "v", "status": status, "idea_id": idea_id,
                               "cost_breakdown": {}, "cost_usd": 0,
                               "updated_at": (T - timedelta(minutes=minutes_ago)).isoformat()})[0]


def _job(w, v, status="running", attempts=1, **extra):
    return w.insert("jobs", {"type": "produce_video", "status": status, "attempts": attempts, "max_attempts": 3,
                             "payload": {"video_id": v["id"]}, "video_id": v["id"], "channel_id": w.ch["id"],
                             "locked_by": f"{config.WORKER_ID}:heavy", **extra})[0]


def test_failed_video_returns_its_idea_then_retires_it(world, monkeypatch):
    idea = world.insert("ideas", {"channel_id": world.ch["id"], "title": "x", "status": "queued", "fail_count": 0})[0]

    def boom(*a, **k):
        raise PermanentError("bad topic")
    monkeypatch.setattr(main.pipeline, "produce", boom)
    main.run_one(_job(world, _video(world, idea_id=idea["id"])))
    i = world.select("ideas", {"id": idea["id"]}, single=True)
    assert (i["status"], i["fail_count"]) == ("new", 1)
    main.run_one(_job(world, _video(world, idea_id=idea["id"])))
    assert world.select("ideas", {"id": idea["id"]}, single=True)["status"] == "retired"


def test_sweeper_fails_orphaned_videos_only(world):
    orphan = _video(world, "rendering", minutes_ago=20)
    alive = _video(world, "rendering", minutes_ago=20)
    _job(world, alive)
    fresh = _video(world, "queued", minutes_ago=5)
    assert ops.sweep_stuck_videos(T) == 1
    assert world.select("videos", {"id": orphan["id"]}, single=True)["status"] == "failed"
    assert world.select("videos", {"id": alive["id"]}, single=True)["status"] == "rendering"
    assert world.select("videos", {"id": fresh["id"]}, single=True)["status"] == "queued"


def test_startup_reset_honours_max_attempts(world):
    spent, ok = _video(world, "rendering"), _video(world, "visuals")
    j1, j2 = _job(world, spent, attempts=3), _job(world, ok, attempts=1)
    main.reset_stale_jobs()
    assert world.select("jobs", {"id": j1["id"]}, single=True)["status"] == "failed"
    assert world.select("videos", {"id": spent["id"]}, single=True)["status"] == "failed"
    assert world.select("jobs", {"id": j2["id"]}, single=True)["status"] == "queued"
