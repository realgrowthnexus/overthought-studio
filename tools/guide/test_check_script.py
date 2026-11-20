import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_script  # noqa: E402


def _write(tmp_path, scene):
    p = tmp_path / "s.yaml"
    import yaml
    p.write_text(yaml.safe_dump({"chapters": [{"id": 1, "title_roman": "T", "scenes": [scene]}]}, allow_unicode=True))
    return p


BASE = {"id": "a", "route": "/", "actions": [], "roman": ["Yeh overview hai."], "urdu": ["یہ اوورویو ہے۔"]}


def test_count_mismatch_raises(tmp_path):
    with pytest.raises(ValueError, match="a"):
        check_script.load(_write(tmp_path, {**BASE, "roman": ["Ek.", "Do."]}))


def test_missing_end_mark_raises(tmp_path):
    with pytest.raises(ValueError, match="a"):
        check_script.load(_write(tmp_path, {**BASE, "urdu": ["یہ اوورویو ہے"]}))


def test_long_roman_line_raises(tmp_path):
    with pytest.raises(ValueError, match="a"):
        check_script.load(_write(tmp_path, {**BASE, "roman": ["x" * 85]}))


def test_real_script_is_valid():
    data = check_script.load(HERE / "script.yaml")
    assert len(data["chapters"]) == 10
    words = sum(len(u.split()) for ch in data["chapters"] for sc in ch["scenes"] for u in sc["urdu"])
    assert 600 <= words <= 950, words      # ≈1.6 spoken words/s at rate -8% → 8–11 min with pauses
