"""Planner breaker (A3) and planning without ideas (A4)."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import scheduler

from fakes import install, seed_channel

T = datetime.now(timezone.utc)
STOP = "Stopped making new videos"


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.update("channels", {"id": w.ch["id"]}, {"timezone": "UTC", "post_times": ["09:00", "19:00"], "posts_per_day": 2,
                                              "buffer_days": 1})
    w.insert("ideas", {"channel_id": w.ch["id"], "title": "Doorways", "status": "new", "score": 5})
    return w


def _fail(w, hours_ago: float, n: int = 3):
    for i in range(n):
        w.insert("videos", {"channel_id": w.ch["id"], "title": f"f{i}", "status": "failed", "error": "boom",
                            "updated_at": (T - timedelta(hours=hours_ago)).isoformat()})


def _ch(w, **vals):
    w.update("channels", {"id": w.ch["id"]}, vals)
    return w.select("channels", {"id": w.ch["id"]}, single=True)


def _jobs(w, type_):
    return [j for j in w.tables["jobs"] if j["type"] == type_]


def test_channel_row_updates_do_not_forgive_failures(world):
    _fail(world, 2)
    ch = _ch(world, updated_at=(T - timedelta(hours=1)).isoformat(), failures_forgiven_at=None, blocked_reason=None)
    scheduler._channel(ch, T)
    assert (world.select("channels", {"id": ch["id"]}, single=True)["blocked_reason"] or "").startswith(STOP)
    assert not _jobs(world, "plan_channel")


def test_resume_forgives(world):
    _fail(world, 2)
    ch = _ch(world, failures_forgiven_at=(T - timedelta(minutes=30)).isoformat(), blocked_reason=None)
    scheduler._channel(ch, T)
    assert not world.select("channels", {"id": ch["id"]}, single=True).get("blocked_reason")
    assert _jobs(world, "plan_channel")


def test_breaker_untrips_when_failures_age_out(world):
    _fail(world, 25)
    ch = _ch(world, blocked_reason=f"{STOP}: 3 failed in the last 24h (last error: boom).")
    scheduler._channel(ch, T)
    assert world.select("channels", {"id": ch["id"]}, single=True)["blocked_reason"] is None
    assert any(e["message"].startswith("Planning resumed") for e in world.tables["events"])


def test_no_ideas_means_no_plan_job(world):
    world.tables["ideas"].clear()
    scheduler._channel(world.select("channels", {"id": world.ch["id"]}, single=True), T)
    assert not _jobs(world, "plan_channel")
    assert _jobs(world, "research_ideas")
