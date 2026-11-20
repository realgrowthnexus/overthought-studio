"""Claude subscription limits: a limit is a calm pause with a known resume time, never a failure."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import main, ops
from studio.services import LimitReached

from fakes import install, seed_channel, seed_video


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.insert("services", {"name": "anthropic", "status": "ok"})
    return w


def _job(w, v, waits=0):
    return w.insert("jobs", {"type": "produce_video", "status": "running", "attempts": 1, "max_attempts": 3,
                             "payload": {"video_id": v["id"]}, "video_id": v["id"], "waits": waits,
                             "channel_id": w.ch["id"]})[0]


def test_limit_parks_without_counting_toward_give_up(world):
    v = seed_video(world, world.ch)
    job = _job(world, v, waits=main.MAX_WAITS)          # would give up if this counted as a normal wait
    resume = datetime.now(timezone.utc) + timedelta(hours=2)
    world.fail_next["anthropic"] = LimitReached("anthropic", "5-hour limit reached", resume)
    main.run_one(job)
    j = world.select("jobs", {"id": job["id"]}, single=True)
    assert (j["status"], j["waiting_on"], j["waits"]) == ("waiting", "anthropic", main.MAX_WAITS)
    assert j["prev_video_status"] == "researching"          # the stage it reached is kept
    svc = world.select("services", {"name": "anthropic"}, single=True)
    assert svc["status"] == "warning" and svc["details"]["limited"] is True
    assert svc["details"]["resume_at"] == resume.isoformat()
    ch = world.select("channels", {"id": world.ch["id"]}, single=True)
    assert ch["blocked_reason"].startswith("Claude limit reached")
    ev = [e for e in world.tables["events"] if "limit" in (e.get("message") or "").lower()]
    assert ev and all(e["level"] != "error" for e in ev)


def test_limited_service_resumes_only_after_reset(world):
    v = seed_video(world, world.ch)
    job = _job(world, v)
    resume = datetime.now(timezone.utc) + timedelta(hours=1)
    world.fail_next["anthropic"] = LimitReached("anthropic", "weekly limit reached", resume)
    main.run_one(job)
    ops._resume_waiting()
    assert world.select("jobs", {"id": job["id"]}, single=True)["status"] == "waiting"
    world.update("services", {"name": "anthropic"}, {"details": {"limited": True, "resume_at": (datetime.now(timezone.utc)
                                                                               - timedelta(minutes=1)).isoformat()}})
    ops._resume_waiting()
    assert world.select("jobs", {"id": job["id"]}, single=True)["status"] == "queued"


def _signed_in(monkeypatch, ok=True):
    from studio import claude_cli, llm
    monkeypatch.setattr(llm, "backend", lambda: "subscription")
    monkeypatch.setattr(claude_cli, "auth_ok", lambda: ok)
    from studio import usage
    monkeypatch.setattr(usage, "read", lambda: None)              # no network in tests


def test_health_on_subscription_reports_connected(world, monkeypatch):
    _signed_in(monkeypatch)
    assert ops._health_anthropic() == "ok"
    svc = world.select("services", {"name": "anthropic"}, single=True)
    assert svc["status"] == "ok" and "subscription" in svc["message"]


def test_health_not_signed_in_shows_the_connect_command(world, monkeypatch):
    _signed_in(monkeypatch, ok=False)
    out = {}
    ops._section("anthropic", ops._health_anthropic, out)
    svc = world.select("services", {"name": "anthropic"}, single=True)
    assert svc["status"] == "unconfigured" and "connect-claude.sh" in svc["message"]


def test_health_keeps_an_active_limit_and_clears_it_after_reset(world, monkeypatch):
    _signed_in(monkeypatch)
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    world.update("services", {"name": "anthropic"}, {"status": "warning", "details": {"limited": True, "resume_at": future}})
    assert ops._health_anthropic() == "warning"
    assert world.select("services", {"name": "anthropic"}, single=True)["details"]["limited"] is True
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    world.update("services", {"name": "anthropic"}, {"details": {"limited": True, "resume_at": past}})
    assert ops._health_anthropic() == "ok"
    d = world.select("services", {"name": "anthropic"}, single=True)["details"]
    assert not d.get("limited")
