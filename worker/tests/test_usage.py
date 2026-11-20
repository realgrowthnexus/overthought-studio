"""Reading the Claude plan's limits, measuring what one video costs, and deciding when to pace."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from studio import secrets, usage

from fakes import install, seed_channel, seed_video

SAMPLE = {"five_hour": {"utilization": 41.0, "resets_at": "2026-11-20T20:40:00+00:00"},
          "seven_day": {"utilization": 12.5, "resets_at": "2026-11-23T14:00:00+00:00"},
          "seven_day_opus": None, "extra_usage": {"is_enabled": False}}


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.insert("services", {"name": "anthropic", "status": "ok", "details": {}})
    monkeypatch.setattr(secrets, "get", lambda k: "sk-ant-oat01-x" if k == "claude_oauth_token" else None)
    return w


def _serve(monkeypatch, status=200, body=None, seen=None):
    def handler(req: httpx.Request):
        if seen is not None:
            seen.append(req)
        return httpx.Response(status, json=body if body is not None else SAMPLE)
    monkeypatch.setattr(usage, "_http", lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def test_read_parses_both_windows_and_sends_the_sign_in(world, monkeypatch):
    seen = []
    _serve(monkeypatch, seen=seen)
    r = usage.read()
    assert r["five_hour"] == {"pct": 41.0, "resets_at": "2026-11-20T20:40:00+00:00"}
    assert r["seven_day"]["pct"] == 12.5 and r["source"] == "reported"
    assert seen[0].headers["authorization"] == "Bearer sk-ant-oat01-x"
    assert seen[0].headers["anthropic-beta"] == "oauth-2025-04-20"


@pytest.mark.parametrize("status,body", [(500, {}), (200, {"weird": 1}), (200, {"five_hour": "x"})])
def test_read_failure_gives_none(world, monkeypatch, status, body):
    _serve(monkeypatch, status, body)
    assert usage.read() is None


def test_refresh_keeps_the_last_reading_as_estimate_when_reading_fails(world, monkeypatch):
    _serve(monkeypatch)
    usage.refresh()
    d = world.select("services", {"name": "anthropic"}, single=True)["details"]
    assert d["seven_day"]["pct"] == 12.5 and d["source"] == "reported"
    _serve(monkeypatch, 500, {})
    usage.refresh()
    d = world.select("services", {"name": "anthropic"}, single=True)["details"]
    assert d["seven_day"]["pct"] == 12.5 and d["source"] == "estimate"


def test_per_video_cost_is_measured_from_its_own_runs(world, monkeypatch):
    v = seed_video(world, world.ch)
    pct = {"v": 10.0}
    monkeypatch.setattr(usage, "read", lambda: {"five_hour": {"pct": 1, "resets_at": None},
                                                 "seven_day": {"pct": pct["v"], "resets_at": "2026-11-23T14:00:00+00:00"},
                                                 "source": "reported"})
    usage.before_run(v["id"])
    pct["v"] = 11.0
    usage.after_run(v["id"])
    usage.before_run(v["id"])                     # second run of the same video keeps the first start
    pct["v"] = 12.0
    usage.after_run(v["id"])
    world.update("videos", {"id": v["id"]}, {"status": "ready"})
    usage.refresh()
    assert world.select("services", {"name": "anthropic"}, single=True)["details"]["per_video_pct"] == 2.0


def _details(world, **d):
    world.update("services", {"name": "anthropic"}, {"details": d})


def test_pacing_off_without_a_reported_measurement(world):
    _details(world, source="estimate", seven_day={"pct": 99, "resets_at": None}, per_video_pct=5)
    assert usage.pacing_on() is False
    _details(world, source="reported", seven_day={"pct": 50, "resets_at": "2026-11-23T14:00:00+00:00"})
    assert usage.pacing_on() is False             # no per-video number yet


def test_pacing_turns_on_when_the_week_would_run_out(world, monkeypatch):
    reset = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    monkeypatch.setattr(usage, "remaining_slots", lambda until: 10)
    _details(world, source="reported", seven_day={"pct": 50, "resets_at": reset}, per_video_pct=4.5)
    assert usage.pacing_on() is True              # 50 + 10*4.5 = 95 → at the line
    _details(world, source="reported", seven_day={"pct": 50, "resets_at": reset}, per_video_pct=4.4)
    assert usage.pacing_on() is False             # 94


def test_remaining_slots_counts_every_active_channels_post_times(world):
    world.update("channels", {"id": world.ch["id"]}, {"status": "active", "posts_per_day": 2,
                                                      "post_times": ["09:00", "19:00"], "timezone": "UTC"})
    n = usage.remaining_slots(datetime.now(timezone.utc) + timedelta(days=3))
    assert 5 <= n <= 7
