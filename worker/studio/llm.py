"""Claude API wrapper: structured outputs, web research, cost tracking, and error → service-status mapping."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from . import claude_cli, db, secrets, settings, spend, usage
from .log import event, log
from .services import LimitReached, NotConfigured, OutOfCredits, ServiceDown, limit_active, report_problem, set_status

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


# The owner's rule: Claude never runs above Sonnet, and always at medium effort, on every path (plan or API key).
MODEL_ALIAS = "sonnet"
API_MODEL = "claude-sonnet-5-5"
EFFORT = "medium"


def backend() -> str:
    """'subscription' (Claude Code signed in with the owner's Claude plan) unless an API key is saved AND opted in,
    or the plan's usage limit is in force and the owner allowed a capped API-key fallback (see fallback_room)."""
    if settings.get().get("llm_backend") == "api" and secrets.get("anthropic_api_key"):
        return "api"
    if _limited() and fallback_room():
        return "api"
    return "subscription"


def _limited() -> bool:
    try:
        return limit_active(db.select("services", {"name": "anthropic"}, single=True))
    except Exception:
        return False


def fallback_spent_today() -> float:
    """API-key spend during the last 24 h (subscription runs are recorded at $0, so this is fallback spend)."""
    return spend.total_since(datetime.now(timezone.utc) - timedelta(hours=24), "anthropic")


def fallback_room() -> bool:
    """True when the owner switched on 'continue on the API key when the Claude limit is hit', a key is saved and
    the daily fallback cap still has room. The cap is the hard stop: over it, work parks until the limit resets."""
    s = settings.get()
    if not s.get("api_fallback") or not secrets.get("anthropic_api_key"):
        return False
    cap = float(s.get("api_fallback_daily_usd") or 0)
    return cap > 0 and fallback_spent_today() < cap


def _fallback_or_raise(p: LimitReached, purpose: str, channel_id, video_id) -> None:
    """The plan hit its limit mid-call: keep going on the API key if allowed, else park calmly (re-raise)."""
    if not fallback_room():
        raise p
    report_problem(p)                                   # dashboard still shows the limit and its reset time
    cap = float(settings.get().get("api_fallback_daily_usd") or 0)
    event(f"Claude plan limit reached — continuing '{purpose}' on the API key (daily cap ${cap:.2f})", "warn",
          "services", channel_id=channel_id, video_id=video_id)


def _sub_run(prompt: str, *, system: str, schema: dict, tools: list[str], purpose: str, channel_id, video_id) -> dict:
    """One subscription run, bracketed by limit readings so the cost of each video can be measured."""
    try:
        usage.before_run(video_id)
    except Exception as ex:
        log.info(f"usage before-run skipped: {ex}")
    try:
        out = claude_cli.run(prompt, system=system, schema=schema, tools=tools, model=MODEL_ALIAS, effort=EFFORT)
    except NotConfigured:
        _mark_auth(rejected=True)                   # health check must not flip back to "ok" on token presence alone
        raise
    _mark_auth(rejected=False)
    try:
        usage.after_run(video_id)
    except Exception as ex:
        log.info(f"usage after-run skipped: {ex}")
    _sub_account(out, purpose, channel_id, video_id)
    return out


def _mark_auth(rejected: bool) -> None:
    try:
        d = usage.details()
        if bool(d.get("auth_rejected")) != rejected:
            d["auth_rejected"] = rejected
            usage._save(d)
    except Exception as ex:
        log.info(f"auth mark skipped: {ex}")


def _sub_account(out: dict, purpose: str, channel_id, video_id) -> None:
    try:
        spend.record("anthropic", 0.0, units=(out.get("usage") or {}).get("output_tokens"), unit="output_tokens",
                     detail=f"{purpose} (subscription)", channel_id=channel_id, video_id=video_id)
    except Exception as ex:
        log.warning(f"spend record failed: {ex}")


class _Sources(BaseModel):
    url: str
    title: str = ""
    quote: str = ""


class _Research(BaseModel):
    notes: str
    sources: list[_Sources] = []


RESEARCH_SUFFIX = ("\n\nUse web search and fetch real pages. Put everything you found in `notes` (full detail, with "
                   "the source named next to each fact) and list every page you relied on in `sources` with its "
                   "exact URL, title and a short quote from it.")


def model_cfg() -> tuple[str, str]:
    """Fixed by the owner: Sonnet at medium effort. Stored settings can't raise it."""
    return API_MODEL, EFFORT


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
        if not _limited():                              # on the fallback, keep showing the plan's limit
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
               max_tokens: int = 16000, channel_id=None, video_id=None,
               allow_fallback: bool = True) -> tuple[T, float]:
    """One call that returns a validated Pydantic object. allow_fallback=False never spends on the API key because
    the plan's limit is hit (the assistant waits for the reset instead)."""
    be = backend()
    if be == "api" and not allow_fallback and settings.get().get("llm_backend") != "api":
        be = "subscription"                     # limit in force: the plan call below raises LimitReached calmly
    if be == "subscription":
        try:
            out = _sub_run(prompt, system=system, schema=schema.model_json_schema(), tools=[], purpose=purpose,
                           channel_id=channel_id, video_id=video_id)
        except LimitReached as p:
            if not allow_fallback:
                raise
            _fallback_or_raise(p, purpose, channel_id, video_id)
        else:
            if out.get("structured") is None:
                raise RuntimeError(f"Claude returned no structured output for {purpose}")
            return schema.model_validate(out["structured"]), 0.0
    client = _get_client()
    model, default_effort = model_cfg()
    try:
        resp = client.beta.messages.parse(
            model=model, max_tokens=max_tokens,
            betas=[FALLBACK_BETA], fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={"effort": default_effort},
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
    out = None
    if backend() == "subscription":
        try:
            out = _sub_run(prompt + RESEARCH_SUFFIX, system=system, schema=_Research.model_json_schema(),
                           tools=["WebSearch", "WebFetch"], purpose=purpose, channel_id=channel_id, video_id=video_id)
        except LimitReached as p:
            _fallback_or_raise(p, purpose, channel_id, video_id)
    if out is not None:
        if out.get("structured") is None:
            raise RuntimeError(f"Claude returned no structured research for {purpose} (will retry)")
        r = _Research.model_validate(out["structured"])
        if not r.notes.strip() or not r.sources:
            raise RuntimeError(f"Claude's {purpose} came back without notes or sources (will retry)")
        seen, cites = set(), []
        for src in r.sources:
            if src.url and src.url not in seen:
                seen.add(src.url)
                cites.append({"url": src.url, "title": src.title, "cited_text": src.quote[:400]})
        return r.notes.strip(), cites, 0.0
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
                thinking={"type": "adaptive"}, output_config={"effort": default_effort},
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
    """Cheap health check — counts tokens (free) to validate the key; on the subscription, the CLI's auth status."""
    if backend() == "subscription":
        t0 = time.time()
        if not claude_cli.auth_ok():
            raise NotConfigured("anthropic", "Claude is not signed in")
        return {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "backend": "subscription"}
    client = _get_client()
    model, _ = model_cfg()
    t0 = time.time()
    try:
        r = client.messages.count_tokens(model=model, messages=[{"role": "user", "content": "ping"}])
    except anthropic.APIError as e:
        raise _map_error(e) from e
    return {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "tokens": r.input_tokens}
