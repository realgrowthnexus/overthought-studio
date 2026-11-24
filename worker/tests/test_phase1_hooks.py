"""stop_after test hook, stage timings, and a redo stage applied only once (audit A1)."""
import pytest

from studio import main, ops, pipeline

from fakes import install, seed_channel, seed_video


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    return w


def test_stop_after_script_makes_two_claude_calls_and_spends_nothing_else(world):
    v = seed_video(world, world.ch)
    out = pipeline.produce(v["id"], stop_after="script")
    assert out["status"] == "rejected" and out["approval"] == "rejected"
    assert out["stage_detail"] == "Test stopped after script"
    assert dict(world.calls) == {"claude": 2}
    ev = [e for e in world.tables["events"] if e["message"].startswith("Test run stopped after script")]
    assert ev and set(ev[-1]["data"]["seconds"]) >= {"research", "script"}


def test_plan_channel_passes_stop_after(world):
    world.insert("ideas", {"channel_id": world.ch["id"], "title": "Doorways", "status": "new", "score": 5})
    ops.plan_channel(world.ch["id"], force=True, stop_after="script")
    job = next(j for j in world.tables["jobs"] if j["type"] == "produce_video")
    assert job["payload"]["stop_after"] == "script"


def test_handle_passes_stop_after_from_payload(world):
    v = seed_video(world, world.ch)
    main.handle({"id": 1, "type": "produce_video", "payload": {"video_id": v["id"], "stop_after": "research"}})
    assert world.select("videos", {"id": v["id"]}, single=True)["stage_detail"] == "Test stopped after research"


def test_from_stage_is_applied_once(world):
    v = seed_video(world, world.ch)
    pipeline.produce(v["id"], stop_after="script")              # research + script exist now
    world.update("videos", {"id": v["id"]}, {"status": "failed"})
    job = world.insert("jobs", {"type": "produce_video", "status": "running", "attempts": 1, "max_attempts": 3,
                                "payload": {"video_id": v["id"], "from_stage": "script"}, "video_id": v["id"],
                                "channel_id": world.ch["id"]})[0]
    world.fail_next["runpod"] = RuntimeError("network blip")
    before = world.calls["claude"]
    main.run_one(job)
    j = world.select("jobs", {"id": job["id"]}, single=True)
    assert j["status"] == "queued" and "from_stage" not in j["payload"]
    after_first = world.calls["claude"]
    assert after_first > before                                   # the script was rewritten once
    main.run_one(j)
    assert world.calls["claude"] == after_first                   # resume does not rewrite it again
