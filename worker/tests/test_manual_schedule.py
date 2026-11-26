"""A11: post times the owner sets by hand are kept, reserve their slot, and overdue ones still go out."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import scheduler

from fakes import install, seed_channel

T = datetime.now(timezone.utc)


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.update("channels", {"id": w.ch["id"]}, {"timezone": "UTC", "post_times": ["09:00", "19:00"], "posts_per_day": 2,
                                              "buffer_days": 1})
    w.ch = w.select("channels", {"id": w.ch["id"]}, single=True)
    return w


def _vid(w, **vals):
    base = {"channel_id": w.ch["id"], "title": "v", "status": "approved", "created_at": T.isoformat()}
    return w.insert("videos", {**base, **vals})[0]


def _get(w, v):
    return w.select("videos", {"id": v["id"]}, single=True)


def test_locked_time_on_approved_video_is_kept(world):
    when = (T + timedelta(hours=5, minutes=7)).replace(second=0, microsecond=0).isoformat()
    v = _vid(world, scheduled_for=when, schedule_locked=True)
    scheduler._channel(world.ch, T)
    got = _get(world, v)
    assert got["status"] == "scheduled"
    assert got["scheduled_for"] == when
    assert "UTC" in got["stage_detail"]


def test_locked_time_reserves_the_nearest_slot(world):
    first = scheduler.slots(world.ch, 1)[0]
    _vid(world, status="scheduled", scheduled_for=(first + timedelta(minutes=10)).isoformat(), schedule_locked=True)
    other = _vid(world)
    scheduler._channel(world.ch, T)
    got = _get(world, other)
    assert got["status"] == "scheduled"
    assert got["scheduled_for"] != first.isoformat()          # the hand-picked time took that slot
    assert got["schedule_locked"] is False


def test_overdue_locked_videos_are_not_moved(world):
    a = _vid(world, status="scheduled", scheduled_for=(T - timedelta(minutes=30)).isoformat(), schedule_locked=True)
    b = _vid(world, status="scheduled", scheduled_for=(T - timedelta(minutes=20)).isoformat(), schedule_locked=True)
    scheduler._channel(world.ch, T)
    pubs = [j for j in world.tables["jobs"] if j["type"] == "publish_video"]
    assert [j["payload"]["video_id"] for j in pubs] == [a["id"]]      # one per tick
    assert _get(world, b)["scheduled_for"] == b["scheduled_for"]      # still due, goes out next tick


def test_overdue_unlocked_extras_still_move(world):
    _vid(world, status="scheduled", scheduled_for=(T - timedelta(minutes=30)).isoformat())
    b = _vid(world, status="scheduled", scheduled_for=(T - timedelta(minutes=20)).isoformat())
    scheduler._channel(world.ch, T)
    assert datetime.fromisoformat(_get(world, b)["scheduled_for"]) > T


def test_make_thumb_grabs_the_picked_frame(world):
    import subprocess
    from studio import pipeline
    v = _vid(world, status="ready", cover_ms=1500, duration_s=2.0, video_path="x/preview.mp4")
    lib = pipeline.library_path(v["id"])
    lib.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=108x192:rate=10",
                    "-t", "2", "-pix_fmt", "yuv420p", str(lib)], check=True)
    res = pipeline.make_thumb(v["id"])
    assert res["ms"] == 1500
    key = f"videos/{world.ch['slug']}/{v['id']}/thumb.jpg"
    assert world.storage[key][:2] == b"\xff\xd8"                 # a JPEG
    assert _get(world, v)["thumb_path"].endswith("/thumb.jpg")


def test_make_thumb_without_a_cover_does_nothing(world):
    from studio import pipeline
    v = _vid(world, status="ready")
    assert pipeline.make_thumb(v["id"]) == {"skipped": "no cover picked"}


def test_stale_locked_time_on_reapproved_video_is_not_reused(world):
    v = _vid(world, scheduled_for=(T - timedelta(hours=2)).isoformat(), schedule_locked=True)
    scheduler._channel(world.ch, T)
    assert not [j for j in world.tables["jobs"] if j["type"] == "publish_video"]
    got = _get(world, v)
    assert got["schedule_locked"] is False and datetime.fromisoformat(got["scheduled_for"]) > T
