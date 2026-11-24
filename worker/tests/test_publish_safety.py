"""Phase 3 publish safety: a TikTok rate limit waits 3 h (A9); repeated failures stop retrying (A10)."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import main, ops, pipeline, tiktok

from fakes import install, seed_channel


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.update("channels", {"id": w.ch["id"]}, {"tiktok_account_id": "acct", "posting_mode": "draft", "require_approval": False})
    w.v = w.insert("videos", {"channel_id": w.ch["id"], "title": "t", "status": "scheduled", "caption": "c",
                              "hashtags": ["#a"], "scheduled_for": datetime.now(timezone.utc).isoformat(),
                              "video_path": "x/preview.mp4", "cost_breakdown": {}, "cost_usd": 0})[0]
    monkeypatch.setattr(pipeline, "final_video", lambda v, ch: b"mp4")
    return w


def _raise(code):
    def post(*a, **k):
        raise tiktok.TikTokError(code, "nope")
    return post


def _job(w):
    return w.insert("jobs", {"type": "publish_video", "status": "running", "attempts": 1, "max_attempts": 3,
                             "payload": {"video_id": w.v["id"]}, "video_id": w.v["id"], "channel_id": w.ch["id"],
                             "dedupe_key": f"publish:{w.v['id']}"})[0]


def test_rate_limit_moves_the_post_3h_later(world, monkeypatch):
    monkeypatch.setattr(tiktok, "post_video", _raise("spam_risk_too_many_posts"))
    res = ops.publish_video(world.v["id"])
    v = world.select("videos", {"id": world.v["id"]}, single=True)
    assert res.get("retry") and v["status"] == "scheduled"
    later = datetime.fromisoformat(v["scheduled_for"]) - datetime.now(timezone.utc)
    assert timedelta(hours=2, minutes=50) < later < timedelta(hours=3, minutes=10)
    assert not [j for j in world.tables["jobs"] if j["type"] == "publish_video"]


def test_third_publish_failure_fails_the_video(world, monkeypatch):
    monkeypatch.setattr(tiktok, "post_video", _raise("internal_error"))
    for _ in range(3):
        world.update("videos", {"id": world.v["id"]}, {"status": "scheduled"})
        main.run_one(_job(world))
    v = world.select("videos", {"id": world.v["id"]}, single=True)
    assert v["status"] == "failed" and v["error"].startswith("Publishing failed 3 times")
