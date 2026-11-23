"""`python -m studio.cli smoke`: one line that says which paid service works, without exposing keys."""
import json

from studio import cli, db, llm, ops, voice
from studio.services import NotConfigured

from fakes import install, seed_channel


def _healthy_except_anthropic(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    seed_channel(w)

    def no_key():
        raise NotConfigured("anthropic", "No Anthropic API key saved")

    monkeypatch.setattr(llm, "ping", no_key)
    monkeypatch.setattr(voice, "check", lambda: {"seconds": 1.9, "words": 4})
    monkeypatch.setattr(ops, "_health_runpod", lambda: "balance $12.40")
    return w


def test_smoke_reports_each_part_independently(monkeypatch, tmp_path):
    _healthy_except_anthropic(monkeypatch, tmp_path)
    result = cli.smoke()
    assert result["anthropic"]["ok"] is False
    assert "No Anthropic API key saved" in result["anthropic"]["error"]
    assert result["supabase"]["ok"] is True and result["supabase"]["channels"] == 1
    assert result["voice"]["ok"] is True and result["runpod"]["ok"] is True
    assert result["ffmpeg"]["ok"] is True


def test_smoke_exit_code_and_single_json_line(monkeypatch, tmp_path, capsys):
    _healthy_except_anthropic(monkeypatch, tmp_path)
    assert cli.run(["smoke"]) == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert json.loads(out[-1])["anthropic"]["ok"] is False


def test_smoke_never_prints_key_material(monkeypatch, tmp_path, capsys):
    _healthy_except_anthropic(monkeypatch, tmp_path)

    def leaky():
        raise RuntimeError("401 for key sk-ant-api03-SECRETSECRET")

    monkeypatch.setattr(llm, "ping", leaky)
    cli.run(["smoke"])
    assert "SECRETSECRET" not in capsys.readouterr().out
