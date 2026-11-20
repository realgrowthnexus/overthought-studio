"""`python -m studio.cli claude-token` (used by infra/connect-claude.sh) and `claude-status` (used by doctor.sh)."""
import io

import pytest

from studio import cli, crypto, ops, secrets

from fakes import install, seed_channel

TOKEN = "sk-ant-oat01-AbC_def-123456789012345678901234567890"


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    seed_channel(w)
    secrets.clear_cache()
    monkeypatch.setattr(ops, "health_check", lambda: {"anthropic": "ok"})
    return w


def test_valid_token_is_stored_encrypted(world, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("\x1b[0m" + TOKEN + "\r\n"))
    assert cli.run(["claude-token"]) == 0
    row = world.select("secrets", {"key": "claude_oauth_token"}, single=True)
    assert row["ciphertext"] != TOKEN and crypto.decrypt(row["ciphertext"]) == TOKEN
    assert row["hint"] == TOKEN[-4:]
    out = capsys.readouterr().out
    assert TOKEN not in out and "connected" in out.lower()


@pytest.mark.parametrize("bad", ["", "hello", "sk-ant-api03-notasubscriptiontoken", "sk-ant-oat01-short"])
def test_garbage_is_rejected(world, monkeypatch, bad):
    monkeypatch.setattr("sys.stdin", io.StringIO(bad))
    assert cli.run(["claude-token"]) == 1
    assert not world.select("secrets", {"key": "claude_oauth_token"})


def test_status_line_never_prints_the_token(world, monkeypatch, capsys):
    world.insert("secrets", {"key": "claude_oauth_token", "ciphertext": crypto.encrypt(TOKEN), "hint": "7890"})
    world.update("services", {"name": "anthropic"}, {"status": "ok", "details": {
        "five_hour": {"pct": 41, "resets_at": None}, "seven_day": {"pct": 12, "resets_at": None}}})
    monkeypatch.setattr(cli.claude_cli, "auth_ok", lambda: True)
    assert cli.run(["claude-status"]) == 0
    out = capsys.readouterr().out
    assert TOKEN not in out and "connected" in out and "41%" in out and "12%" in out
