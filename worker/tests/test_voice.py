"""Kokoro voice: sentence chunking, voice config, word timings (fake engine) and one real-model run if present."""
import os

import numpy as np
import pytest

from studio import voice


class _Tok:
    def phonemize(self, w, lang="en-us"):
        return "" if w in ("—", "-") else w.lower().strip(".,!?")

    def tokenize(self, ph, limit=None):
        return [1] * len(ph)


class _FakeEngine:
    """Every token lasts 10 frames → 10 × 240 samples = 0.1 s."""
    def __init__(self):
        import threading
        self.tok = _Tok()
        self.lock = threading.Lock()
        self.voices = type("V", (), {"files": ["af_heart"]})()

    def style(self, name):
        return np.zeros((510, 1, 256), np.float32)

    def run(self, ids, style, speed):
        dur = np.full(len(ids) + 2, 10.0)
        return np.full(int(dur.sum()) * 240, 0.1, np.float32), dur


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(voice, "engine", lambda: _FakeEngine())
    monkeypatch.setattr(voice, "set_status", lambda *a, **k: None)


def test_chunks_split_sentences_and_long_clauses():
    out = voice._chunks("Hi there. You forgot why you came in! Really?  Yes.")
    assert [c for c, _ in out] == ["Hi there.", "You forgot why you came in!", "Really?", "Yes."]
    long = "a word, " * 50 + "end."
    parts = voice._chunks(long)
    assert len(parts) > 1 and parts[-1][1] == voice.SENTENCE_PAUSE and parts[0][1] == voice.CLAUSE_PAUSE


def test_voice_name_defaults_and_legacy_configs():
    assert voice.voice_name({"provider": "kokoro", "voice": "bm_george"}) == "bm_george"
    assert voice.voice_name({"provider": "elevenlabs", "voice_id": "x"}) == voice.DEFAULT_VOICE
    assert voice.voice_name(None) == voice.DEFAULT_VOICE
    assert voice.DEFAULT_VOICE in voice.CATALOG


def test_word_timings_follow_token_durations(fake):
    samples, words = voice.render_speech("Hi you. Go — now.", "af_heart")
    assert [w.text for w in words] == ["Hi", "you.", "Go", "—", "now."]
    lead = 0.12
    # "hi"=2 tokens, then a space token, "you"=3 tokens; pad token first (0.1 s)
    assert words[0].start == pytest.approx(lead + 0.1) and words[0].end == pytest.approx(lead + 0.3)
    assert words[1].start == pytest.approx(lead + 0.4) and words[1].end == pytest.approx(lead + 0.7)
    assert words[3].start == words[3].end                          # silent dash: zero-length
    assert all(b.start >= a.start for a, b in zip(words, words[1:]))
    assert words[2].start > words[1].end + voice.SENTENCE_PAUSE - 1e-6
    assert len(samples) / voice.SR >= words[-1].end
    assert float(np.max(np.abs(samples))) == pytest.approx(0.89, rel=1e-3)


def test_synthesize_returns_mp3_and_zero_cost(fake):
    mp3, words, cost = voice.synthesize("One short line.", {"provider": "kokoro", "voice": "af_heart"})
    assert cost == 0.0 and len(words) == 3
    assert mp3[:3] == b"ID3" or mp3[0] == 0xFF


def test_missing_model_is_not_configured(monkeypatch, tmp_path):
    from studio.services import NotConfigured
    monkeypatch.setattr(voice, "_engine", None)
    monkeypatch.setattr(voice, "MODEL", tmp_path / "nope.onnx")
    with pytest.raises(NotConfigured):
        voice.engine()


@pytest.mark.skipif(not voice.MODEL.exists(), reason="Kokoro model not downloaded (set STUDIO_KOKORO_DIR)")
def test_real_model_speaks_with_word_timings():
    samples, words = voice.render_speech("In 2011, a study at Notre Dame found this. Try it.", "am_michael+am_fenrir")
    assert [w.text for w in words][:2] == ["In", "2011,"]
    assert 2.0 < len(samples) / voice.SR < 8.0
    assert words[0].start < 0.6 and words[-1].end <= len(samples) / voice.SR
