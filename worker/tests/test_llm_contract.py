"""Pins the exact Claude API requests the worker sends, against canned API responses (no network)."""
import json

import httpx2 as httpx
import pytest

from studio import content, llm, settings
from studio.services import NotConfigured, OutOfCredits

SCORE = {"hook": 9, "curiosity_gap": 8, "viewer_question": 8, "emotional_connection": 8, "clarity": 9, "pacing": 8,
         "accuracy_framing": 9, "loop": 8, "originality": 7, "overall": 8.4, "biggest_risk": "slow middle",
         "fixes": ["cut beat 5"]}


def _msg(content_blocks, stop="end_turn", **extra):
    body = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": content_blocks, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 50}}
    body.update(extra)
    return body


class Api:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return httpx.Response(status, json=body)

    def body(self, i=0) -> dict:
        return json.loads(self.requests[i].content)


@pytest.fixture
def api(monkeypatch):
    holder = {}

    def use(*responses):
        a = Api(*responses)
        client = llm._make_client("sk-test", http_client=httpx.Client(transport=httpx.MockTransport(a)))
        monkeypatch.setattr(llm, "_get_client", lambda: client)
        holder["api"] = a
        return a

    monkeypatch.setattr(settings, "get", lambda *a, **k: dict(settings.DEFAULTS))
    monkeypatch.setattr(llm, "backend", lambda: "api")          # these tests pin the API-key path
    monkeypatch.setattr(llm.spend, "record", lambda *a, **k: None)
    monkeypatch.setattr(llm, "set_status", lambda *a, **k: None)
    return use


def test_structured_request_shape(api):
    a = api((200, _msg([{"type": "text", "text": json.dumps(SCORE)}])))
    card, usd = llm.structured(content.Scorecard, "SYSTEM", "score this", purpose="scorecard")
    b = a.body()
    assert b["model"] == "claude-sonnet-5-5"
    assert b["thinking"] == {"type": "adaptive"}
    assert b["output_config"]["effort"] == "medium"
    assert b["output_config"]["format"]["type"] == "json_schema"
    assert b["fallbacks"] == "default"
    assert b["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "server-side-fallback-2026-07-01" in a.requests[0].headers["anthropic-beta"]
    assert not {"temperature", "top_p", "budget_tokens", "output_format"} & set(b)
    assert isinstance(card, content.Scorecard) and card.overall == 8.4 and usd > 0


CITE = {"type": "web_search_result_location", "url": "https://doi.org/x", "title": "Paper", "cited_text": "found",
        "encrypted_index": "e"}


def test_research_handles_pause_turn_and_citations(api):
    a = api((200, _msg([{"type": "text", "text": "searching"}], stop="pause_turn")),
            (200, _msg([{"type": "text", "text": "Radvansky 2011", "citations": [CITE, dict(CITE)]}],
                       usage={"input_tokens": 100, "output_tokens": 50,
                              "server_tool_use": {"web_search_requests": 2}})))
    text, cites, usd = llm.research("SYS", "find it", purpose="research")
    assert len(a.requests) == 2
    assert a.body(1)["messages"][-1]["role"] == "assistant"
    assert a.body(0)["tools"][0]["type"] == "web_search_20260209"
    assert text == "Radvansky 2011" and cites == [{"url": "https://doi.org/x", "title": "Paper", "cited_text": "found"}]
    assert usd >= 2 * llm.WEB_SEARCH_USD


def test_research_large_max_tokens_is_allowed(api):
    a = api((200, _msg([{"type": "text", "text": "ok"}])))
    text, _, _ = llm.research("SYS", "find it", purpose="research")
    assert text == "ok" and a.body()["max_tokens"] >= 32000


def test_refusal_raises_readable_error(api):
    api((200, _msg([], stop="refusal", stop_details={"type": "refusal", "category": "cyber",
                                                     "explanation": "declined"})))
    with pytest.raises(RuntimeError, match="declined"):
        llm.structured(content.Scorecard, "S", "p", purpose="scorecard")


def test_low_credit_maps_to_out_of_credits(api):
    api((400, {"type": "error", "error": {"type": "invalid_request_error",
                                          "message": "Your credit balance is too low to access the Anthropic API."}}))
    with pytest.raises(OutOfCredits):
        llm.structured(content.Scorecard, "S", "p", purpose="scorecard")


def test_bad_key_maps_to_not_configured(api):
    api((401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}))
    with pytest.raises(NotConfigured):
        llm.structured(content.Scorecard, "S", "p", purpose="scorecard")
