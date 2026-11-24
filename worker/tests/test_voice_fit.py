"""Phase 3: voice lands in the window by measured pace + a speed nudge; rewrites are the rare fallback."""
import pytest

from studio import content, pipeline

from fakes import install, seed_channel, seed_video


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    return w


def test_word_range_follows_speed():
    a = {"min_seconds": 65, "max_seconds": 95, "voice": {"wps": 2.0, "speed": 1.1}}
    b = {"min_seconds": 65, "max_seconds": 95, "voice": {"wps": 2.2}}
    assert content.word_range(a) == content.word_range(b)
    assert content.effective_wps(a) == pytest.approx(2.2)


def test_long_voice_is_fixed_by_speed_not_rewrite(world, monkeypatch):
    speeds = []
    real = world.synthesize

    def synth(text, voice_cfg, **k):
        speeds.append(float((voice_cfg or {}).get("speed") or 1.0))
        if len(speeds) == 1:
            world.voice_seconds = [110.0]
        else:
            world.voice_seconds = [110.0 / speeds[-1] * 0.82]   # faster speech, and pace scaled to land in range
        return real(text, voice_cfg, **k)
    monkeypatch.setattr(pipeline.voice, "synthesize", synth)
    v = seed_video(world, world.ch)
    pipeline.produce(v["id"], stop_after="voice")
    assert len(speeds) == 2 and 1.0 < speeds[1] <= 1.10
    assert world.schemas.count("Script") == 1                     # no rewrite


def test_still_out_of_range_rewrites_once(world, monkeypatch):
    real = world.synthesize
    n = {"i": 0}

    def synth(text, voice_cfg, **k):
        n["i"] += 1
        world.voice_seconds = [130.0] if n["i"] <= 2 else [80.0]
        return real(text, voice_cfg, **k)
    monkeypatch.setattr(pipeline.voice, "synthesize", synth)
    v = seed_video(world, world.ch)
    out = pipeline.produce(v["id"], stop_after="voice")
    assert world.schemas.count("Script") == 2 and world.schemas.count("PolicyCheck") == 2
    assert out["stage_detail"] == "Test stopped after voice"


def test_wps_is_learned_and_averaged(world):
    v = seed_video(world, world.ch)
    pipeline.produce(v["id"], stop_after="voice")
    ch = world.select("channels", {"id": world.ch["id"]}, single=True)
    assert ch["voice"]["wps_n"] == 1 and ch["voice"]["wps"] == pytest.approx(2.1, rel=0.1)
    first = ch["voice"]["wps"]
    pipeline._learn_wps(ch, words=200, seconds=100.0, speed=1.0)
    ch = world.select("channels", {"id": world.ch["id"]}, single=True)
    assert ch["voice"]["wps_n"] == 2 and ch["voice"]["wps"] == pytest.approx((first + 2.0) / 2, abs=1e-3)
