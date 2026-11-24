"""Phase 2 visuals: scenes drawn in parallel, partial failures keep finished scenes, redo never reuses old files."""
import time

import pytest

from studio import content, pipeline

from fakes import install, seed_channel, seed_video


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    return w


def _five_scenes(world):
    from fakes import clean_script
    base = clean_script()
    base.scenes = [content.Scene(id=i, description=f"scene {i}") for i in range(5)]
    for i, b in enumerate(base.beats):
        b.scene_id = i % 5
    world.script_factory = lambda: base


def test_scenes_are_drawn_in_parallel(world, monkeypatch):
    _five_scenes(world)
    real = world.generate

    def slow(*a, **k):
        time.sleep(0.3)
        return real(*a, **k)
    monkeypatch.setattr(pipeline.images, "generate", slow)
    v = seed_video(world, world.ch)
    pipeline.produce(v["id"], stop_after="script")
    world.update("videos", {"id": v["id"]}, {"status": "scripting"})
    t0 = time.monotonic()
    pipeline.produce(v["id"], stop_after="visuals")
    assert time.monotonic() - t0 < 1.2
    assert world.calls["runpod"] == 5


def test_one_failed_scene_keeps_the_others(world, monkeypatch):
    _five_scenes(world)
    real = world.generate
    state = {"n": 0}

    def flaky(description, **k):
        state["n"] += 1
        if "scene 2" in description and state["n"] <= 5:
            raise RuntimeError("one image failed")
        return real(description, **k)
    monkeypatch.setattr(pipeline.images, "generate", flaky)
    v = seed_video(world, world.ch)
    with pytest.raises(RuntimeError):
        pipeline.produce(v["id"], stop_after="visuals")
    slug = world.ch["slug"]
    saved = [k for k in world.storage if f"{v['id']}/scenes/" in k]
    assert len(saved) == 4
    before = world.calls["runpod"]
    pipeline.produce(v["id"], stop_after="visuals")
    assert world.calls["runpod"] == before + 1                       # only the missing scene is drawn


def test_redo_from_script_draws_new_scenes(world):
    v = seed_video(world, world.ch)
    pipeline.produce(v["id"], stop_after="visuals")
    n = world.calls["runpod"]
    pipeline.produce(v["id"], "script", stop_after="visuals")
    assert world.calls["runpod"] == 2 * n


def test_redo_from_voice_records_new_voice(world):
    v = seed_video(world, world.ch)
    pipeline.produce(v["id"], stop_after="voice")
    n = world.calls["voice"]
    pipeline.produce(v["id"], "voice", stop_after="voice")
    assert world.calls["voice"] == 2 * n
    assert world.select("videos", {"id": v["id"]}, single=True)["audio_path"]      # set again by the new voice
