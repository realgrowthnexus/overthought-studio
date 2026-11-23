"""Storage stays inside Supabase's free plan: full video on the VPS disk, small preview in Supabase, cleanup."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import ops, pipeline

from fakes import install, seed_channel, seed_video


@pytest.fixture
def made(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    ch = seed_channel(w)
    v = pipeline.produce(seed_video(w, ch)["id"])
    return w, ch, v


def test_publish_reads_disk_copy_and_rerenders_when_it_is_gone(made, monkeypatch):
    w, ch, v = made
    first = pipeline.final_video(v, ch)
    assert first == pipeline.library_path(v["id"]).read_bytes()
    calls = {"n": 0}
    real = pipeline._render

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(pipeline, "_render", counting)
    pipeline.library_path(v["id"]).unlink()                        # new VPS / disk wiped
    again = pipeline.final_video(v, ch)
    assert calls["n"] == 1 and len(again) > 100_000
    assert pipeline.library_path(v["id"]).exists()
    assert w.calls["runpod"] == 4 and w.calls["voice"] == 1         # nothing paid twice


def test_cleanup_after_posting(made):
    w, ch, v = made
    base = f"videos/{ch['slug']}/{v['id']}"
    long_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    w.update("videos", {"id": v["id"]}, {"status": "posted", "posted_at": long_ago})
    assert any(k.startswith(f"{base}/scenes/") for k in w.storage)
    res = ops.cleanup_storage()
    assert res["videos_cleaned"] == 1 and res["library_files_removed"] == 1
    assert not pipeline.library_path(v["id"]).exists()
    assert f"{base}/preview.mp4" not in w.storage and f"{base}/voice.mp3" not in w.storage
    assert not any(k.startswith(f"{base}/scenes/") for k in w.storage)
    assert f"{base}/thumb.jpg" in w.storage                         # thumbnails stay for the dashboard


def test_cleanup_keeps_unposted_videos(made):
    w, ch, v = made
    res = ops.cleanup_storage()
    assert res["videos_cleaned"] == 0 and res["library_files_removed"] == 0
    assert pipeline.library_path(v["id"]).exists()
    assert f"videos/{ch['slug']}/{v['id']}/preview.mp4" in w.storage


def test_regenerate_render_drops_old_disk_copy(made, monkeypatch):
    w, ch, v = made
    seen = {}
    real = pipeline._render

    def spy(video, c, work):
        seen["existed"] = pipeline.library_path(video["id"]).exists()
        return real(video, c, work)

    monkeypatch.setattr(pipeline, "_render", spy)
    pipeline.produce(v["id"], from_stage="render")
    assert seen["existed"] is False and pipeline.library_path(v["id"]).exists()
