"""Phase 1 script stage: length target from the voice's real speed, code-side checks, only sources research found."""
import copy

from studio import content, pipeline

from fakes import clean_script

CH = {"min_seconds": 65, "max_seconds": 95, "voice": {}}


def test_word_range_uses_midpoint_and_wps():
    assert content.word_range(CH) == (155, 181)
    assert content.word_range({**CH, "voice": {"wps": 2.5}}) == (184, 216)
    assert content.word_range({"min_seconds": 50, "max_seconds": 60, "voice": {}}) == (129, 148)


def _fitting_script() -> content.Script:
    s = clean_script()
    lo, hi = content.word_range(CH)
    per = (lo + hi) // 2 // len(s.beats)
    for b in s.beats:
        b.narration = " ".join(["word"] * per)
    return s


def test_script_problems_flags_structure_and_length():
    assert content.script_problems(_fitting_script(), CH) == []
    bad = _fitting_script()
    bad.beats = bad.beats[:6]
    bad.beats[-1].kind = "payoff"
    bad.beats[2].scene_id = 9
    probs = " ".join(content.script_problems(bad, CH)).lower()
    assert "beats" in probs and "loop" in probs and "scene" in probs
    long = _fitting_script()
    long.beats[1].narration += " extra" * 80
    assert any("words" in p.lower() for p in content.script_problems(long, CH))


def test_keep_found_sources_normalises_urls():
    s = clean_script()
    s.sources[0].url = "http://doi.org/10.1/x"
    s.sources.append(content.Source(researcher="Nobody", institution="", year=2020, finding="made up",
                                    url="https://example.com/fake", replication="not_tested"))
    s.beats[5].source_index = 1
    out = content.keep_found_sources(s, [{"url": "https://www.doi.org/10.1/x/", "title": "t", "cited_text": ""}])
    assert [x.researcher for x in out.sources] == ["Radvansky"]
    assert out.beats[5].source_index is None
    assert out.beats[4].source_index == 0          # the study beat still points at the kept source


def test_old_script_without_self_review_still_loads():
    d = clean_script().model_dump()
    d.pop("self_review", None)
    for src in d["sources"]:
        src.pop("institution", None)
    assert content.Script.model_validate(copy.deepcopy(d)).self_review is None


def test_source_label_is_researcher_and_year():
    assert pipeline._source_label({"researcher": "Radvansky", "institution": "X", "year": 2011}) == "→ Radvansky · 2011"
