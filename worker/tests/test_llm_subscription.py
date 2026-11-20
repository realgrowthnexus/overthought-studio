"""llm.py on the subscription backend: same signatures, routed through the headless CLI (fake)."""
import json

import pytest

from studio import claude_cli, content, llm, secrets, settings
from studio.services import NotConfigured

from test_llm_contract import SCORE

FAKE = __import__("pathlib").Path(__file__).with_name("fake_claude.py")


@pytest.fixture
def sub(monkeypatch, tmp_path):
    log = tmp_path / "calls.jsonl"
    monkeypatch.setattr(claude_cli, "CLAUDE_BIN", str(FAKE))
    monkeypatch.setattr(claude_cli.config, "WORK", tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    keys = {"claude_oauth_token": "sk-ant-oat01-x"}
    monkeypatch.setattr(secrets, "get", lambda k: keys.get(k))
    sets = {**settings.DEFAULTS}
    monkeypatch.setattr(settings, "get", lambda *a, **k: sets)
    spent = []
    monkeypatch.setattr(llm.spend, "record", lambda *a, **k: spent.append((a, k)))
    monkeypatch.setattr(llm, "set_status", lambda *a, **k: None)
    calls = lambda: [json.loads(l)["argv"] for l in log.read_text().splitlines()]
    return monkeypatch, calls, keys, sets, spent


def test_backend_defaults_to_subscription_even_with_a_saved_key(sub):
    mp, calls, keys, sets, _ = sub
    keys["anthropic_api_key"] = "sk-ant-api03-x"
    assert llm.backend() == "subscription"
    sets["llm_backend"] = "api"
    assert llm.backend() == "api"
    del keys["anthropic_api_key"]
    assert llm.backend() == "subscription"            # opt-in without a key never switches


def test_structured_goes_through_cli_and_costs_nothing(sub):
    mp, calls, _, _, spent = sub
    mp.setenv("FAKE_CLAUDE_STRUCTURED", json.dumps(SCORE))
    card, usd = llm.structured(content.Scorecard, "SYSTEM", "score this", purpose="scorecard", video_id="v1")
    assert card.overall == 8.4 and usd == 0.0
    a = calls()[-1]
    assert json.loads(a[a.index("--json-schema") + 1])["properties"]["overall"]
    assert a[a.index("--model") + 1] == "sonnet"        # light work saves limit
    assert spent and spent[-1][0][1] == 0.0


def test_heavy_work_uses_the_plans_default_model(sub):
    mp, calls, _, _, _ = sub
    mp.setenv("FAKE_CLAUDE_STRUCTURED", json.dumps({"notes": "n", "sources": []}))
    llm.research("SYS", "find it", purpose="research")
    assert "--model" not in calls()[-1]


def test_research_returns_notes_and_citations(sub):
    mp, calls, _, _, _ = sub
    mp.setenv("FAKE_CLAUDE_STRUCTURED", json.dumps(
        {"notes": "Doorways reset memory.", "sources": [{"url": "https://x.org/a", "title": "A", "quote": "q"},
                                                         {"url": "https://x.org/a", "title": "dup", "quote": ""}]}))
    text, cites, usd = llm.research("SYS", "find it", purpose="research")
    assert text == "Doorways reset memory." and usd == 0.0
    assert cites == [{"url": "https://x.org/a", "title": "A", "cited_text": "q"}]
    a = calls()[-1]
    assert a[a.index("--tools") + 1] == "WebSearch,WebFetch"


def test_ping_uses_no_model_call(sub):
    mp, calls, keys, _, _ = sub
    assert llm.ping()["ok"] is True
    assert calls()[-1][:2] == ["auth", "status"]
    keys.clear()
    with pytest.raises(NotConfigured):
        llm.ping()
