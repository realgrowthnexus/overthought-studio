import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose  # noqa: E402

SCRIPT = {"chapters": [
    {"id": 1, "title_roman": "Ek", "scenes": [{"id": "1.1"}, {"id": "1.2"}]},
    {"id": 2, "title_roman": "Do", "scenes": [{"id": "2.1"}]},
]}
NARR = {"1.1": {"duration": 10.0, "cues": [[0.0, 4.0, "a"], [4.7, 9.0, "b"]]},
        "1.2": {"duration": 5.0, "cues": [[0.0, 4.0, "c"]]},
        "2.1": {"duration": 6.0, "cues": [[0.5, 5.0, "d"]]}}


def test_timeline_offsets_include_title_cards():
    segs, cues, chapters = compose.build_timeline(SCRIPT, NARR, title_s=3.0)
    assert [s["kind"] for s in segs] == ["title", "scene", "scene", "title", "scene"]
    assert [s["start"] for s in segs] == [0.0, 3.0, 13.0, 18.0, 21.0]
    assert [(c.start, c.roman) for c in cues] == [(3.0, "a"), (7.7, "b"), (13.0, "c"), (21.5, "d")]
    assert chapters == [(0.0, "Ek"), (18.0, "Do")]


def test_chapter_list_format():
    assert compose.chapter_lines([(0.0, "Ek"), (75.4, "Do")]) == "00:00 1. Ek\n01:15 2. Do\n"


def test_short_clip_is_refused(tmp_path):
    import json
    import pytest
    (tmp_path / "1.1.json").write_text(json.dumps({"duration": 9.0}))
    with pytest.raises(ValueError, match="1.1"):
        compose.check_clip("1.1", tmp_path, audio_duration=10.0)
    (tmp_path / "1.2.json").write_text(json.dumps({"duration": 10.0}))
    compose.check_clip("1.2", tmp_path, audio_duration=10.02)
