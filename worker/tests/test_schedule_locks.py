"""Owner-set post times are kept (A11), and the cover frame becomes the thumbnail."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import ops, scheduler

from fakes import install, seed_channel

T = datetime.now(timezone.utc)


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.update("channels", {"id": w.ch["id"]}, {"timezone": "America/New_York", "post_times": ["09:00", "19:00"],
                                              "posts_per_day": 2, "buffer_days": 1})
    w.insert("ideas", {"channel_id": w.ch["id"], "title": "i", "status": "new", "score": 5})
    return w


def _ch(w):
    return w.select("channels", {"id": w.ch["id"]}, single=True)


def _v(w, **vals):
    return w.insert("videos", {"channel_id": w.ch["id"], "title": "v", "created_at": T.isoformat(), **vals})[0]


def test_locked_time_on_approved_video_is_kept(world):
    when = (T + timedelta(hours=5, minutes=7)).replace(microsecond=0).isoformat()
    v = _v(world, status="approved", scheduled_for=when, schedule_locked=True)
    scheduler._channel(_ch(world), T)
    got = world.select("videos", {"id": v["id"]}, single=True)
    assert got["status"] == "scheduled" and got["scheduled_for"] == when


def test_locked_time_reserves_its_slot(world):
    slot = scheduler.slots(_ch(world), 1)[0]
    locked = _v(world, status="scheduled", scheduled_for=slot.isoformat(), schedule_locked=True)
    other = _v(world, status="approved")
    scheduler._channel(_ch(world), T)
    got = world.select("videos", {"id": other["id"]}, single=True)
    assert got["status"] == "scheduled" and got["scheduled_for"][:16] != slot.isoformat()[:16]
    assert world.select("videos", {"id": locked["id"]}, single=True)["scheduled_for"] == slot.isoformat()


def test_overdue_locked_videos_are_not_moved(world):
    a = _v(world, status="scheduled", scheduled_for=(T - timedelta(hours=2)).isoformat(), schedule_locked=True)
    b = _v(world, status="scheduled", scheduled_for=(T - timedelta(hours=1)).isoformat(), schedule_locked=True)
    scheduler._channel(_ch(world), T)
    pubs = [j for j in world.tables["jobs"] if j["type"] == "publish_video"]
    assert [j["video_id"] for j in pubs] == [a["id"]]
    assert world.select("videos", {"id": b["id"]}, single=True)["scheduled_for"] == (T - timedelta(hours=1)).isoformat()


def test_schedule_label_uses_the_channel_timezone(world):
    v = _v(world, status="approved")
    world.update("channels", {"id": world.ch["id"]}, {"timezone": "America/Los_Angeles"})
    scheduler._channel(_ch(world), T)
    detail = world.select("videos", {"id": v["id"]}, single=True)["stage_detail"]
    assert detail.endswith(("PST", "PDT")) and "ET" not in detail


def test_make_thumb_uploads_frame_at_cover_ms(world, tmp_path, monkeypatch):
    import subprocess
    clip = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=108x192:rate=10", "-t", "3",
                    "-pix_fmt", "yuv420p", str(clip)], check=True)
    v = _v(world, status="ready", cover_ms=1500, video_path=f"{world.ch['slug']}/x/preview.mp4")
    monkeypatch.setattr(ops, "_cover_source", lambda video: clip)
    ops.make_thumb(v["id"])
    key = f"videos/{world.ch['slug']}/{v['id']}/thumb.jpg"
    assert world.storage[key][:2] == b"\xff\xd8"
    assert world.select("videos", {"id": v["id"]}, single=True)["thumb_path"] == f"{world.ch['slug']}/{v['id']}/thumb.jpg"
