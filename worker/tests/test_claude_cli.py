"""The headless Claude Code runner, against a fake CLI (no real Claude calls)."""
import json
from datetime import datetime, timezone

import pytest

from studio import claude_cli, secrets
from studio.services import LimitReached, NotConfigured

FAKE = __import__("pathlib").Path(__file__).with_name("fake_claude.py")
TOKEN = "sk-ant-oat01-testtoken_ABC"


@pytest.fixture
def cli(monkeypatch, tmp_path):
    log = tmp_path / "calls.jsonl"
    monkeypatch.setattr(claude_cli, "CLAUDE_BIN", str(FAKE))
    monkeypatch.setattr(claude_cli.config, "WORK", tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api-should-not-leak")
    monkeypatch.setattr(secrets, "get", lambda k: TOKEN if k == "claude_oauth_token" else None)
    calls = lambda: [json.loads(l) for l in log.read_text().splitlines()]
    return monkeypatch, calls


def test_structured_success_and_argv(cli):
    mp, calls = cli
    mp.setenv("FAKE_CLAUDE_STRUCTURED", json.dumps({"score": 8}))
    out = claude_cli.run("rate it", system="SYS", schema={"type": "object"}, tools=[], model="sonnet")
    assert out["structured"] == {"score": 8} and out["usage"]["output_tokens"] == 42
    c = calls()[-1]
    a = c["argv"]
    assert a[0] == "-p" and "--json-schema" in a and a[a.index("--model") + 1] == "sonnet"
    assert a[a.index("--tools") + 1] == ""                       # no built-in tools at all
    assert a[a.index("--system-prompt") + 1] == "SYS"
    assert TOKEN not in json.dumps(a)                            # token only via env
    assert c["token"] == TOKEN and c["api_key"] is None         # an API key never outranks the sign-in


def test_research_allows_only_web_tools(cli):
    mp, calls = cli
    claude_cli.run("look it up", system="S", schema=None, tools=["WebSearch", "WebFetch"], model="opus")
    a = calls()[-1]["argv"]
    assert a[a.index("--tools") + 1] == "WebSearch,WebFetch"


def test_limit_with_epoch_raises_limit_reached(cli):
    mp, _ = cli
    mp.setenv("FAKE_CLAUDE_MODE", "limit")
    with pytest.raises(LimitReached) as e:
        claude_cli.run("x", system="S", schema=None, tools=[], model="opus")
    assert e.value.resume_at == datetime.fromtimestamp(1900000000, timezone.utc)


def test_limit_text_raises_limit_reached_with_future_resume(cli):
    mp, _ = cli
    mp.setenv("FAKE_CLAUDE_MODE", "limit_text")
    with pytest.raises(LimitReached) as e:
        claude_cli.run("x", system="S", schema=None, tools=[], model="opus")
    assert e.value.resume_at > datetime.now(timezone.utc)


def test_auth_error_means_not_signed_in(cli):
    mp, _ = cli
    mp.setenv("FAKE_CLAUDE_MODE", "auth")
    with pytest.raises(NotConfigured):
        claude_cli.run("x", system="S", schema=None, tools=[], model="opus")


def test_other_errors_are_retryable_runtime_errors(cli):
    mp, _ = cli
    for mode in ("error", "garbage"):
        mp.setenv("FAKE_CLAUDE_MODE", mode)
        with pytest.raises(RuntimeError) as e:
            claude_cli.run("x", system="S", schema=None, tools=[], model="opus")
        assert TOKEN not in str(e.value)


def test_no_token_means_not_signed_in(cli):
    mp, _ = cli
    mp.setattr(secrets, "get", lambda k: None)
    mp.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    with pytest.raises(NotConfigured):
        claude_cli.run("x", system="S", schema=None, tools=[], model="opus")
    assert claude_cli.auth_ok() is False


def test_auth_ok_with_token(cli):
    assert claude_cli.auth_ok() is True


def test_overload_parks_as_service_down_not_a_retry_burning_error(cli):
    from studio.services import ServiceDown
    mp, _ = cli
    mp.setenv("FAKE_CLAUDE_MODE", "overloaded")
    with pytest.raises(ServiceDown):
        claude_cli.run("x", system="S", schema=None, tools=[], model="opus")


def test_limit_clock_text_gives_that_reset_time(cli):
    mp, _ = cli
    mp.setenv("FAKE_CLAUDE_MODE", "limit_clock")
    with pytest.raises(LimitReached) as e:
        claude_cli.run("x", system="S", schema=None, tools=[], model="opus")
    ra = e.value.resume_at
    assert (ra.hour, ra.minute) == (15, 0) and ra > datetime.now(timezone.utc)


def test_parse_reset_clock_rolls_to_tomorrow_when_past():
    now = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)
    t = claude_cli.parse_reset("resets 3pm (UTC)", now)
    assert t == datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)
    assert claude_cli.parse_reset("resets 9:30am (America/New_York)", now).hour == 14
    assert claude_cli.parse_reset("no time here", now) is None


@pytest.mark.parametrize("text", ["Claude Code failed: You've hit your 5-hour limit · resets 1:50pm (UTC)",
                                  "You've hit your 5 hour limit · resets 2pm (UTC)",
                                  "You've reached your usage limit · resets 9pm (UTC)"])
def test_real_limit_wordings_are_limits(text):
    assert claude_cli._LIMIT.search(text)
    assert claude_cli.parse_reset(text) is not None
