"""Runs Claude Code headless (`claude -p`), signed in with the owner's Claude subscription.

The sign-in token lives encrypted in `secrets` (key `claude_oauth_token`) and reaches the CLI only through the
subprocess environment, never argv. Limits raise LimitReached (a calm pause), a missing or rejected sign-in raises
NotConfigured, and anything else raises RuntimeError (retried by the job loop).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

from . import config, secrets
from .services import LimitReached, NotConfigured, ServiceDown

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
TIMEOUT = 900
_STRIP_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN")
_LIMIT = re.compile(r"usage limit reached|hit your (session|weekly|opus|sonnet)? ?limit|limit reached|"
                    r"(session|weekly) limit", re.I)
_AUTH = re.compile(r"/login|invalid api key|oauth token|not logged in|authentication|unauthori[sz]ed|\b401\b", re.I)
_EPOCH = re.compile(r"\|(\d{10})\b")
_CLOCK = re.compile(r"resets\s+(\d{1,2})(?::(\d\d))?\s*([ap]m)\s*\(([^)]+)\)", re.I)
# Anthropic-side trouble (overload, 5xx, rate limit, network): park and resume, never burn retries into a failed video
_TRANSIENT = re.compile(r"overloaded|\b529\b|\b5\d\d\b|rate.?limit|ECONNRESET|ETIMEDOUT|ENOTFOUND|socket hang up|"
                        r"network|connection (error|refused|reset)|fetch failed", re.I)


def parse_reset(text: str, now: datetime | None = None) -> datetime | None:
    """'resets 3pm (America/New_York)' → the next such moment, in UTC."""
    m = _CLOCK.search(text)
    if not m:
        return None
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(m.group(4).strip())
    except Exception:
        return None
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(tz)
    t = local.replace(hour=hour, minute=int(m.group(2) or 0), second=0, microsecond=0)
    if t <= local:
        t += timedelta(days=1)
    return t.astimezone(timezone.utc)


def token() -> str | None:
    t = secrets.get("claude_oauth_token")
    return re.sub(r"[^A-Za-z0-9_-]", "", t) if t else None


def _env(tok: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV}
    home = config.WORK / ".claude-home"
    home.mkdir(parents=True, exist_ok=True)
    env.update(HOME=str(home), CLAUDE_CODE_OAUTH_TOKEN=tok, DISABLE_AUTOUPDATER="1", CLAUDE_CODE_DISABLE_TELEMETRY="1")
    return env


def _resume_at(text: str) -> datetime:
    m = _EPOCH.search(text)
    if m:
        return datetime.fromtimestamp(int(m.group(1)), timezone.utc)
    clock = parse_reset(text)
    if clock:
        return clock
    try:
        from . import usage
        ra = usage.reset_for_limit()
        if ra:
            return ra
    except Exception:
        pass
    return datetime.now(timezone.utc) + timedelta(hours=1)


def run(prompt: str, *, system: str, schema: dict | None, tools: list[str], model: str | None,
        effort: str | None = None, timeout: int = TIMEOUT, with_token: str | None = None) -> dict:
    """One headless Claude Code turn. Returns {text, structured, usage, model}. `with_token` checks a new sign-in."""
    tok = with_token or token()
    if not tok:
        raise NotConfigured("anthropic", "Claude is not signed in")
    argv = [CLAUDE_BIN, "-p", prompt, "--output-format", "json", "--system-prompt", system, "--tools", ",".join(tools), "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config"]
    if model:                                         # None = the plan's default model
        argv += ["--model", model]
    if effort:
        argv += ["--effort", effort]
    if tools:
        argv += ["--allowedTools", ",".join(tools)]
    if schema is not None:
        argv += ["--json-schema", json.dumps(schema)]
    with tempfile.TemporaryDirectory(prefix="claude-run-") as cwd:
        try:
            p = subprocess.run(argv, cwd=cwd, env=_env(tok), capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ServiceDown("anthropic", f"Claude took longer than {timeout // 60} minutes (will retry)") from None
    raw = (p.stdout or "").strip()
    try:
        out = json.loads(raw.splitlines()[-1]) if raw else {}
    except json.JSONDecodeError:
        out = {}
    text = str(out.get("result") or "")
    err_text = text or (p.stderr or "")[-500:]
    if not out or out.get("is_error") or out.get("subtype") != "success":
        if _LIMIT.search(err_text):
            raise LimitReached("anthropic", "Claude usage limit reached", _resume_at(err_text))
        if _TRANSIENT.search(err_text):
            raise ServiceDown("anthropic", "Claude is busy or unreachable right now (will retry)")
        if _AUTH.search(err_text):
            raise NotConfigured("anthropic", "Claude sign-in was rejected — sign in again")
        msg = err_text.replace(tok, "***")[:300] or f"exit code {p.returncode}"
        raise RuntimeError(f"Claude Code failed: {msg}")
    models = list((out.get("modelUsage") or {}).keys())
    return {"text": text, "structured": out.get("structured_output"), "usage": out.get("usage") or {},
            "model": models[0] if models else (model or "default")}


def auth_ok() -> bool:
    """Signed in? Uses the CLI's own status check, which makes no model call and uses no limit."""
    tok = token()
    if not tok:
        return False
    try:
        p = subprocess.run([CLAUDE_BIN, "auth", "status", "--json"], env=_env(tok), capture_output=True, text=True,
                           timeout=30)
        return bool(json.loads(p.stdout or "{}").get("loggedIn"))
    except Exception:
        return True                                  # the token is present; the next real call will tell
