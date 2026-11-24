"""Phase 3 render safety (A8): a killed render child fails fast; a video without audio is an error."""
import os
import time
from concurrent.futures.process import BrokenProcessPool

import pytest

from studio import pipeline
from studio.render import compose


def _die(job):
    os._exit(1)


def test_dead_render_child_raises():
    t0 = time.monotonic()
    with pytest.raises(BrokenProcessPool):
        compose._run_segments(_die, [(0, 1, "a"), (1, 2, "b")], 2)
    assert time.monotonic() - t0 < 30


def test_render_timeout_is_25_minutes():
    assert pipeline.RENDER_TIMEOUT_S == 1500


def test_missing_audio_stream_is_an_error():
    with pytest.raises(RuntimeError, match="audio"):
        pipeline._check_probe({"duration": 80.0, "acodec": None})
    pipeline._check_probe({"duration": 80.0, "acodec": "aac"})
