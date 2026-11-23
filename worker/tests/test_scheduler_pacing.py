"""Weekly pacing (fewer evening videos) and round-robin planning across channels."""
import copy
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from studio import scheduler, usage

from fakes import install, seed_channel

CH = {"timezone": "UTC", "post_times": ["19:00", "09:00"], "posts_per_day": 2}


def test_pacing_keeps_only_the_morning_slot():
    full = scheduler.slots(CH, 3)
    paced = scheduler.slots(CH, 3, pacing=True)
    assert {s.hour for s in paced} == {9}
    assert len(full) > len(paced) >= 3


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    a = seed_channel(w)
    b = copy.deepcopy(a)
    b.update(id=str(uuid.uuid4()), slug="second", name="Second")
    w.tables["channels"].append(b)
    for ch in (a, b):
        w.update("channels", {"id": ch["id"]}, {**CH, "buffer_days": 1})
    w.a, w.b = a, b
    monkeypatch.setattr(usage, "pacing_on", lambda: False)
    return w


def _plans(w):
    return [j["channel_id"] for j in w.tables["jobs"] if j["type"] == "plan_channel"]


def test_round_robin_plans_the_channel_with_nothing_in_production(world):
    world.insert("videos", {"channel_id": world.a["id"], "title": "x", "status": "scripting"})
    scheduler.tick()
    assert _plans(world) == [world.b["id"]]


def test_both_channels_plan_when_equal(world):
    scheduler.tick()
    assert sorted(_plans(world)) == sorted([world.a["id"], world.b["id"]])


def test_pacing_never_moves_a_scheduled_evening_video(world, monkeypatch):
    monkeypatch.setattr(usage, "pacing_on", lambda: True)
    evening = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    v = world.insert("videos", {"channel_id": world.a["id"], "title": "x", "status": "scheduled",
                                "scheduled_for": evening.isoformat()})[0]
    world.insert("videos", {"channel_id": world.a["id"], "title": "y", "status": "approved",
                            "created_at": "2026-01-01T00:00:00+00:00"})
    scheduler.tick()
    assert world.select("videos", {"id": v["id"]}, single=True)["scheduled_for"] == evening.isoformat()
    ap = [x for x in world.tables["videos"] if x["title"] == "y"][0]
    assert ap["status"] == "scheduled" and datetime.fromisoformat(ap["scheduled_for"]).hour == 9


def test_a_stopped_channel_does_not_hold_the_others_back(world):
    world.insert("videos", {"channel_id": world.a["id"], "title": "x", "status": "scripting"})
    world.update("channels", {"id": world.b["id"]}, {"blocked_reason": "Stopped making new videos: 3 failed"})
    scheduler.tick()
    assert world.a["id"] in _plans(world)


def test_a_channel_whose_planning_keeps_failing_does_not_hold_the_others_back(world):
    world.insert("videos", {"channel_id": world.a["id"], "title": "x", "status": "scripting"})
    world.insert("jobs", {"type": "plan_channel", "status": "failed", "channel_id": world.b["id"],
                          "finished_at": datetime.now(timezone.utc).isoformat()})
    scheduler.tick()
    assert world.a["id"] in _plans(world)
