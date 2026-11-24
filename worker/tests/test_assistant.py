"""Dashboard assistant: knows the live studio, proposes only valid whitelisted actions, never spends on the API."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import assistant, llm
from studio.services import LimitReached

from fakes import install, seed_channel


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.insert("secrets", {"key": "runpod_api_key", "value": "v1:SECRETVALUE"})
    w.update("services", {"name": "runpod"}, {"balance": 212.03, "balance_unit": "USD", "message": None})
    w.v = w.insert("videos", {"channel_id": w.ch["id"], "title": "Doorways", "status": "ready", "cost_usd": 0.06})[0]
    w.j = w.insert("jobs", {"type": "produce_video", "status": "failed", "last_error": "boom", "video_id": w.v["id"]})[0]
    return w


def _ask(w, text, reply):
    w.insert("assistant_messages", {"role": "user", "content": text, "status": "done",
                                    "created_at": datetime.now(timezone.utc).isoformat()})
    p = w.insert("assistant_messages", {"role": "assistant", "content": "", "status": "pending",
                                        "created_at": (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()})[0]
    seen = {}

    def fake(schema, system, prompt, **k):
        seen.update(prompt=prompt, system=system, kwargs=k)
        if isinstance(reply, Exception):
            raise reply
        return schema.model_validate(reply), 0.0
    return p, seen, fake


def test_snapshot_has_balances_jobs_videos_and_no_secrets(world):
    snap = assistant.snapshot()
    text = str(snap)
    assert "212.03" in text and "Doorways" in text and "boom" in text and world.ch["slug"] in text
    assert "SECRETVALUE" not in text and "secrets" not in snap


def test_reply_saved_and_invalid_actions_dropped(world, monkeypatch):
    p, seen, fake = _ask(world, "approve the doorway video", {"reply": "Approve karne ke liye button dabayein.", "actions": [
        {"type": "approve_video", "label": "Approve Doorways", "video_id": world.v["id"]},
        {"type": "approve_video", "label": "Ghost", "video_id": "00000000-0000-0000-0000-000000000000"},
        {"type": "delete_everything", "label": "Nope"},
        {"type": "retry_job", "label": "Retry", "job_id": world.j["id"]}]})
    monkeypatch.setattr(llm, "structured", fake)
    assistant.reply(p["id"])
    row = world.select("assistant_messages", {"id": p["id"]}, single=True)
    assert row["status"] == "done" and row["content"].startswith("Approve")
    assert [a["label"] for a in row["actions"]] == ["Approve Doorways", "Retry"]
    assert seen["kwargs"].get("allow_fallback") is False


def test_limit_reached_gives_calm_reply_without_fallback(world, monkeypatch):
    p, _, fake = _ask(world, "hi", LimitReached("anthropic", "limit", datetime(2026, 11, 24, 13, 50, tzinfo=timezone.utc)))
    monkeypatch.setattr(llm, "structured", fake)
    assistant.reply(p["id"])
    row = world.select("assistant_messages", {"id": p["id"]}, single=True)
    assert row["status"] == "done" and "limit" in row["content"].lower() and row["actions"] == []


def test_history_is_included(world, monkeypatch):
    world.insert("assistant_messages", {"role": "user", "content": "what is runpod balance", "status": "done",
                                        "created_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()})
    p, seen, fake = _ask(world, "and now?", {"reply": "ok", "actions": []})
    monkeypatch.setattr(llm, "structured", fake)
    assistant.reply(p["id"])
    assert "what is runpod balance" in seen["prompt"] and "and now?" in seen["prompt"]
