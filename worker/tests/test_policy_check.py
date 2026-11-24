"""Phase 2: the light content check (tone, graphic content, TikTok rules, length) replaces the fact-check."""
import pytest

from studio import content, main, pipeline

from fakes import clean_script, install, seed_channel, seed_video


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    return w


def _job(w, v):
    return w.insert("jobs", {"type": "produce_video", "status": "running", "attempts": 1, "max_attempts": 3,
                             "payload": {"video_id": v["id"]}, "video_id": v["id"], "channel_id": w.ch["id"]})[0]


def test_check_passes_clean_script_with_one_call(world):
    v = seed_video(world, world.ch)
    out = pipeline.produce(v["id"], stop_after="factcheck")
    assert world.calls["claude"] == 3 and out["factcheck"]["passed"] is True


def test_check_problem_gets_one_fix_then_passes(world):
    world.check_blocks = 1
    v = seed_video(world, world.ch)
    out = pipeline.produce(v["id"], stop_after="factcheck")
    assert world.calls["claude"] == 5 and out["factcheck"]["passed"] is True     # check, fix, re-check


def test_check_still_blocked_fails_with_reason(world):
    world.check_blocks = 99
    v = seed_video(world, world.ch)
    main.run_one(_job(world, v))
    vid = world.select("videos", {"id": v["id"]}, single=True)
    assert vid["status"] == "failed" and vid["error"].startswith("Content check failed")


def test_short_script_is_a_problem():
    s = clean_script()
    for b in s.beats:
        b.narration = " ".join(["word"] * 10)
    msg = content.length_problem(s, {"min_seconds": 65, "max_seconds": 90, "voice": {}})
    assert msg and "seconds" in msg
    assert content.length_problem(clean_script(), {"min_seconds": 65, "max_seconds": 90, "voice": {}}) is None


def test_old_factcheck_shape_counts_as_done():
    assert pipeline._fc_done({"blocking": [], "passes": False})
    assert pipeline._fc_done({"passed": True, "problems": []})
    assert not pipeline._fc_done({"passed": False, "problems": [{"issue": "x"}]})


def test_length_rewrite_uses_policy_check(world):
    assert not hasattr(content, "FactCheck") and not hasattr(content, "fact_check")
    world.voice_seconds = [120.0]
    v = seed_video(world, world.ch)
    pipeline.produce(v["id"], stop_after="voice")
    assert world.schemas.count("PolicyCheck") == 2           # the check, then the re-check after the length edit
