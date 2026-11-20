"""Claude API wrapper: structured outputs, web research, cost tracking, and error → service-status mapping."""
from __future__ import annotations

import time
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from . import secrets, settings, spend
from .log import log
from .services import NotConfigured, OutOfCredits, ServiceDown, set_status

T = TypeVar("T", bound=BaseModel)

# $ per 1M tokens (input, output). Cache reads are billed at ~0.05x on current models.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-2": (8.0, 40.0),
}
WEB_SEARCH_USD = 10.0 / 1000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client: anthropic.Anthropic | None = None
_client_key: str | None = None


def _make_client(key: str, http_client=None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=key, max_retries=3, timeout=600, http_client=http_client)


def _get_client() -> anthropic.Anthropic:
    global _client, _client_key
    key = secrets.get("anthropic_api_key")
    if not key:
        raise NotConfigured("anthropic", "No Anthropic API key saved")
    if _client is None or key != _client_key:
        _client = _make_client(key)
        _client_key = key
    return _client


def model_cfg() -> tuple[str, str]:
    s = settings.get()
    return s.get("model") or "claude-opus-5-5", s.get("effort") or "high"


def _cost(model: str, usage: Any) -> float:
    pin, pout = PRICES.get(model, PRICES["claude-opus-5-5"])
    inp = (getattr(usage, "input_tokens", 0) or 0)
    cw = (getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cr = (getattr(usage, "cache_read_input_tokens", 0) or 0)
    out = (getattr(usage, "output_tokens", 0) or 0)
    usd = (inp * pin + cw * pin * 1.25 + cr * pin * 0.05 + out * pout) / 1e6
    stu = getattr(usage, "server_tool_use", None)
    searches = (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
    return usd + searches * WEB_SEARCH_USD


def _map_error(e: Exception) -> Exception:
    msg = str(getattr(e, "message", e))
    low = msg.lower()
    if isinstance(e, anthropic.AuthenticationError):
        return NotConfigured("anthropic", "Anthropic API key is invalid")
    if isinstance(e, (anthropic.BadRequestError, anthropic.PermissionDeniedError)) and (
            "credit balance" in low or "billing" in low or "purchase credits" in low):
        return OutOfCredits("anthropic", "Anthropic credit balance is too low")
    if isinstance(e, anthropic.RateLimitError):
        return ServiceDown("anthropic", "Rate limited by Anthropic (will retry)")
    if isinstance(e, anthropic.APIStatusError) and e.status_code >= 500:
        return ServiceDown("anthropic", f"Anthropic API error {e.status_code} (will retry)")
    if isinstance(e, anthropic.APITimeoutError):
        return RuntimeError("Anthropic request timed out (will retry)")
    if isinstance(e, anthropic.APIConnectionError):
        return ServiceDown("anthropic", "Cannot reach Anthropic API (will retry)")
    return e


def _account(model: str, resp: Any, purpose: str, channel_id, video_id) -> float:
    usd = _cost(resp.model if getattr(resp, "model", None) in PRICES else model, resp.usage)
    try:
        spend.record("anthropic", usd, units=getattr(resp.usage, "output_tokens", None), unit="output_tokens",
                     detail=purpose, channel_id=channel_id, video_id=video_id)
        set_status("anthropic", "ok", None)
    except Exception as ex:
        log.warning(f"spend record failed: {ex}")
    return usd


def _check_stop(resp: Any, purpose: str) -> None:
    if resp.stop_reason == "refusal":
        det = getattr(resp, "stop_details", None)
        raise RuntimeError(f"Claude declined the {purpose} request ({getattr(det, 'category', None)})")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(f"Claude output hit max_tokens during {purpose}")


def structured(schema: type[T], system: str, prompt: str, *, purpose: str, effort: str | None = None,
               max_tokens: int = 16000, channel_id=None, video_id=None) -> tuple[T, float]:
    """One call that returns a validated Pydantic object."""
    client = _get_client()
    model, default_effort = model_cfg()
    try:
        resp = client.beta.messages.parse(
            model=model, max_tokens=max_tokens,
            betas=[FALLBACK_BETA], fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={"effort": effort or default_effort},
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
    except anthropic.APIError as e:
        raise _map_error(e) from e
    usd = _account(model, resp, purpose, channel_id, video_id)
    _check_stop(resp, purpose)
    parsed = resp.parsed_output
    if parsed is None:
        raise RuntimeError(f"Claude returned no structured output for {purpose}")
    return parsed, usd


def research(system: str, prompt: str, *, purpose: str, max_searches: int = 8, effort: str | None = None,
             channel_id=None, video_id=None) -> tuple[str, list[dict], float]:
    """Web-grounded research. Returns (text, citations[{url,title,cited_text}], usd)."""
    client = _get_client()
    model, default_effort = model_cfg()
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches,
              "user_location": {"type": "approximate", "country": "US"}}]
    messages: list[dict] = [{"role": "user", "content": prompt}]
    total = 0.0
    resp = None
    for _ in range(6):                      # resume pause_turn up to 6 times
        try:
            resp = client.beta.messages.create(
                model=model, max_tokens=32000, betas=[FALLBACK_BETA], fallbacks="default",
                thinking={"type": "adaptive"}, output_config={"effort": effort or default_effort},
                system=system, tools=tools, messages=messages,
            )
        except anthropic.APIError as e:
            raise _map_error(e) from e
        total += _account(model, resp, purpose, channel_id, video_id)
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    assert resp is not None
    _check_stop(resp, purpose)
    texts, cites, seen = [], [], set()
    for b in resp.content:
        if b.type == "text":
            texts.append(b.text)
            for c in (getattr(b, "citations", None) or []):
                url = getattr(c, "url", None)
                if url and url not in seen:
                    seen.add(url)
                    cites.append({"url": url, "title": getattr(c, "title", ""),
                                  "cited_text": (getattr(c, "cited_text", "") or "")[:400]})
    return "\n".join(texts).strip(), cites, total


def ping() -> dict:
    """Cheap health check — counts tokens (free) to validate the key."""
    client = _get_client()
    model, _ = model_cfg()
    t0 = time.time()
    try:
        r = client.messages.count_tokens(model=model, messages=[{"role": "user", "content": "ping"}])
    except anthropic.APIError as e:
        raise _map_error(e) from e
    return {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "tokens": r.input_tokens}
