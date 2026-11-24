"""The real production line, end to end, with every paid service faked (no network, no spend)."""
import shutil

import pytest

from studio import main, pipeline
from studio.services import OutOfCredits

from fakes import install, messy_script, probe, seed_channel, seed_video


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    return w


def _final(w, ch, vid) -> bytes:
    return pipeline.library_path(vid).read_bytes()


def test_produce_reaches_ready_and_video_is_over_60s(world):
    v = seed_video(world, world.ch)
    out = pipeline.produce(v["id"])
    assert out["status"] == "ready" and out["approval"] == "pending"
    info = probe(_final(world, world.ch, v["id"]))
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert float(info["format"]["duration"]) > 61
    assert (vs["codec_name"], vs["width"], vs["height"], vs["r_frame_rate"]) == ("h264", 1080, 1920, "30/1")
    base = f"videos/{world.ch['slug']}/{v['id']}"
    assert f"{base}/thumb.jpg" in world.storage
    assert f"{base}/final.mp4" not in world.storage                   # full file stays on the VPS disk
    pv = probe(world.storage[f"{base}/preview.mp4"])
    pvs = next(s for s in pv["streams"] if s["codec_type"] == "video")
    assert (pvs["width"], pvs["height"]) == (540, 960) and float(pv["format"]["duration"]) > 61
    assert len(world.storage[f"{base}/preview.mp4"]) < len(_final(world, world.ch, v["id"]))
    assert out["video_path"] == f"{world.ch['slug']}/{v['id']}/preview.mp4"
    assert out["cost_usd"] > 0


def test_messy_script_still_renders(world):
    world.script_factory = messy_script
    v = seed_video(world, world.ch)
    assert pipeline.produce(v["id"])["status"] == "ready"


def test_resume_after_restart_does_not_repay(world, monkeypatch):
    v = seed_video(world, world.ch)
    real = pipeline._render
    state = {"n": 0}

    def flaky(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("container restarted")
        return real(*a, **k)

    monkeypatch.setattr(pipeline, "_render", flaky)
    with pytest.raises(RuntimeError):
        pipeline.produce(v["id"])
    before = dict(world.calls)
    shutil.rmtree(pipeline.config.WORK / "videos" / v["id"])       # fresh machine
    assert pipeline.produce(v["id"])["status"] == "ready"
    assert dict(world.calls) == before


def test_out_of_credits_parks_job(world):
    v = seed_video(world, world.ch)
    job = world.insert("jobs", {"type": "produce_video", "status": "running", "attempts": 1, "max_attempts": 3,
                                "payload": {"video_id": v["id"]}, "video_id": v["id"],
                                "channel_id": world.ch["id"]})[0]
    world.fail_next["runpod"] = OutOfCredits("runpod", "RunPod balance is empty")
    main.run_one(job)
    j = world.select("jobs", {"id": job["id"]}, single=True)
    assert (j["status"], j["waiting_on"]) == ("waiting", "runpod")
    assert world.select("services", {"name": "runpod"}, single=True)["status"] == "out_of_credits"
    assert world.select("videos", {"id": v["id"]}, single=True)["status"] == "blocked"


def test_factcheck_fails_twice_is_permanent(world):
    world.factcheck_passes = False
    v = seed_video(world, world.ch)
    job = world.insert("jobs", {"type": "produce_video", "status": "running", "attempts": 1, "max_attempts": 3,
                                "payload": {"video_id": v["id"]}, "video_id": v["id"],
                                "channel_id": world.ch["id"]})[0]
    main.run_one(job)
    vid = world.select("videos", {"id": v["id"]}, single=True)
    assert vid["status"] == "failed" and vid["error"].startswith("Fact-check failed")
    assert world.select("jobs", {"id": job["id"]}, single=True)["status"] == "failed"


def test_factcheck_minor_notes_never_block(world):
    world.factcheck_minor = ("Institution is MIT, not Imperial College",)
    v = seed_video(world, world.ch)
    job = world.insert("jobs", {"type": "produce_video", "status": "running", "attempts": 1, "max_attempts": 3,
                                "payload": {"video_id": v["id"]}, "video_id": v["id"],
                                "channel_id": world.ch["id"]})[0]
    main.run_one(job)
    vid = world.select("videos", {"id": v["id"]}, single=True)
    assert vid["status"] not in ("failed", "fact_checking"), vid.get("error")
    assert vid["factcheck"]["minor"] and not vid["factcheck"]["blocking"]
