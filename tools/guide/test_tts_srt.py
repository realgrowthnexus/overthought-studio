import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import srt  # noqa: E402
import tts  # noqa: E402


def test_cues_offset_and_count():
    cues = tts.cues_from_boundaries([(0, 2.0), (2.4, 5.1)], ["Ek.", "Do."], offset=10)
    assert [c.start for c in cues] == [10.0, 12.4]
    assert [c.end for c in cues] == [12.0, 15.1]
    assert [c.roman for c in cues] == ["Ek.", "Do."]


def test_cues_mismatch_raises():
    with pytest.raises(ValueError):
        tts.cues_from_boundaries([(0, 1.0)], ["Ek.", "Do."], offset=0)


def test_srt_format():
    out = srt.to_srt([tts.Cue(10.0, 12.0, "Pehli line."), tts.Cue(3725.5, 3727.25, "Doosri.")])
    assert out.startswith("1\n00:00:10,000 --> 00:00:12,000\nPehli line.\n\n2\n")
    assert "01:02:05,500 --> 01:02:07,250" in out
