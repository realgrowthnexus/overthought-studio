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


def test_failed_idea_is_kept_while_the_owner_can_redo_then_returned(world, monkeypatch):
    idea = world.insert("ideas", {"channel_id": world.ch["id"], "title": "x", "status": "queued", "fail_count": 0})[0]

    def boom(*a, **k):
        raise PermanentError("bad topic")
    monkeypatch.setattr(main.pipeline, "produce", boom)
    v1 = _video(world, idea_id=idea["id"])
    main.run_one(_job(world, v1))
    assert world.select("ideas", {"id": idea["id"]}, single=True)["status"] == "queued"   # owner may press Make again
    world.update("videos", {"id": v1["id"]}, {"updated_at": (T - timedelta(hours=7)).isoformat()})
    ops.release_failed_ideas(T)
    i = world.select("ideas", {"id": idea["id"]}, single=True)
    assert (i["status"], i["fail_count"]) == ("new", 1)
    ops.release_failed_ideas(T)                                                        # counted once, not per tick
    assert world.select("ideas", {"id": idea["id"]}, single=True)["fail_count"] == 1
    world.update("ideas", {"id": idea["id"]}, {"status": "queued"})
    v2 = _video(world, "failed", idea_id=idea["id"], minutes_ago=7 * 60)
    ops.release_failed_ideas(T)
    assert world.select("ideas", {"id": idea["id"]}, single=True)["status"] == "retired"


def test_idea_with_an_active_video_is_not_released(world):
    idea = world.insert("ideas", {"channel_id": world.ch["id"], "title": "x", "status": "queued", "fail_count": 0})[0]
    _video(world, "failed", idea_id=idea["id"], minutes_ago=7 * 60)
    _video(world, "researching", idea_id=idea["id"])
    ops.release_failed_ideas(T)
    assert world.select("ideas", {"id": idea["id"]}, single=True)["status"] == "queued"


def test_parks_do_not_use_up_attempts(world):
    v = _video(world, "visuals")
    j = _job(world, v, attempts=3)
    main._park(j, "anthropic", "limit", "warning", True, count=False)
    assert world.select("jobs", {"id": j["id"]}, single=True)["attempts"] == 2


def test_sweeper_never_touches_a_video_that_moved_on(world, monkeypatch):
    v = _video(world, "rendering", minutes_ago=20)
    real = world.select

    def racing(table, where=None, **k):          # the job finishes right after the stale-video read
        rows = real(table, where, **k)
        if table == "videos" and where and where.get("status") == ("in", ops._SWEEP):
            world.update("videos", {"id": v["id"]}, {"status": "ready", "updated_at": T.isoformat()})
        return rows
    monkeypatch.setattr(ops.db, "select", racing)
    assert ops.sweep_stuck_videos(T) == 0
    assert world.select("videos", {"id": v["id"]}, single=True)["status"] == "ready"


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


def test_not_in_filter_is_sent_as_a_postgrest_list():
    from studio import db
    assert db._filters({"status": ("not.in", ["failed", "rejected"])}) == {"status": 'not.in.("failed","rejected")'}
