"""Claude plan limit hit → optional, capped fallback to the API key (owner opt-in), else the usual calm pause."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from studio import claude_cli, llm, ops, secrets, settings
from studio.services import LimitReached

REAL_STRUCTURED = llm.structured          # fakes.install() replaces it; these tests need the real one

from fakes import install, seed_channel  # noqa: E402


class Card(BaseModel):
    score: int


class _FakeClient:
    def __init__(self):
        self.calls = 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.calls += 1
        use = SimpleNamespace(input_tokens=10_000, output_tokens=2_000, cache_creation_input_tokens=0,
                              cache_read_input_tokens=0, server_tool_use=None)
        return SimpleNamespace(model=kw["model"], usage=use, stop_reason="end_turn", parsed_output=Card(score=9))


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    seed_channel(w)
    monkeypatch.setattr(llm, "structured", REAL_STRUCTURED)
    resume = datetime.now(timezone.utc) + timedelta(hours=3)

    def limited(*a, **k):
        raise LimitReached("anthropic", "Claude usage limit reached", resume)

    monkeypatch.setattr(claude_cli, "run", limited)
    monkeypatch.setattr(secrets, "get", lambda k: "sk-ant-api-test" if k == "anthropic_api_key" else None)
    w.client = _FakeClient()
    monkeypatch.setattr(llm, "_get_client", lambda: w.client)
    w.resume = resume
    return w


def _settings(w, **vals):
    w.insert("settings", {"key": "global", "value": vals}, upsert=True, on_conflict="key")
    settings._cache.clear()


def test_without_opt_in_the_limit_still_parks(world):
    _settings(world, api_fallback=False)
    with pytest.raises(LimitReached):
        llm.structured(Card, "sys", "prompt", purpose="script")
    assert world.client.calls == 0


def test_opt_in_continues_on_the_api_key_and_keeps_showing_the_limit(world):
    _settings(world, api_fallback=True, api_fallback_daily_usd=2)
    card, usd = llm.structured(Card, "sys", "prompt", purpose="script")
    assert card.score == 9 and usd > 0 and world.client.calls == 1
    svc = world.select("services", {"name": "anthropic"}, single=True)
    assert svc["status"] == "warning" and svc["details"]["limited"] is True     # card still says "limit reached"
    assert any("continuing 'script' on the API key" in (e.get("message") or "") for e in world.tables["events"])
    assert llm.backend() == "api"                                                # next calls skip the plan


def test_daily_cap_stops_the_fallback(world):
    _settings(world, api_fallback=True, api_fallback_daily_usd=1)
    world.insert("spend", {"service": "anthropic", "amount_usd": 1.2, "detail": "script"})
    with pytest.raises(LimitReached):
        llm.structured(Card, "sys", "prompt", purpose="script")
    assert world.client.calls == 0
    assert llm.fallback_room() is False


def test_no_api_key_means_no_fallback(world, monkeypatch):
    _settings(world, api_fallback=True, api_fallback_daily_usd=5)
    monkeypatch.setattr(secrets, "get", lambda k: None)
    with pytest.raises(LimitReached):
        llm.structured(Card, "sys", "prompt", purpose="script")


def test_parked_jobs_resume_when_the_fallback_has_room(world):
    _settings(world, api_fallback=False)
    world.update("services", {"name": "anthropic"}, {"status": "warning", "details": {
        "limited": True, "resume_at": world.resume.isoformat()}})
    job = world.insert("jobs", {"type": "produce_video", "status": "waiting", "waiting_on": "anthropic",
                                "parked_status": "limited", "payload": {}})[0]
    ops._resume_waiting()
    assert world.select("jobs", {"id": job["id"]}, single=True)["status"] == "waiting"
    _settings(world, api_fallback=True, api_fallback_daily_usd=2)
    ops._resume_waiting()
    assert world.select("jobs", {"id": job["id"]}, single=True)["status"] == "queued"
