"""The dashboard assistant: snapshot, action whitelist, calm limits, never the paid fallback."""
from datetime import datetime, timedelta, timezone

import pytest

from studio import assistant, llm
from studio.services import LimitReached

from fakes import install, seed_channel

T = datetime.now(timezone.utc)
REAL_STRUCTURED = llm.structured


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    w.ch = seed_channel(w)
    w.update("channels", {"id": w.ch["id"]}, {"tiktok_account_id": "acct-secret-id"})
    w.video = w.insert("videos", {"channel_id": w.ch["id"], "title": "Doorways", "status": "ready"})[0]
    w.insert("jobs", {"id": 77, "type": "produce_video", "status": "waiting", "waiting_on": "runpod"})
    w.calls_args = []
    return w


def _ask(w, text="Studio ka haal batao", rid=2):
    w.insert("assistant_messages", {"id": rid - 1, "role": "user", "content": text, "status": "done"})
    w.insert("assistant_messages", {"id": rid, "role": "assistant", "content": "", "status": "pending"})
    return rid


def _claude(w, monkeypatch, replies):
    seq = list(replies)

    def fake(schema, system, prompt, **kw):
        w.calls_args.append(kw)
        w.calls["claude"] += 1
        r = seq.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, 0.0
    monkeypatch.setattr(llm, "structured", fake)


def _msg(w, rid):
    return w.select("assistant_messages", {"id": rid}, single=True)


def test_snapshot_has_state_but_no_account_ids(world):
    snap = assistant.snapshot()
    assert snap["channels"][0]["name"] == world.ch["name"]
    assert snap["channels"][0]["tiktok_linked"] is True
    assert "acct-secret-id" not in str(snap)
    assert snap["jobs_active"][0]["waiting_on"] == "runpod"
    assert snap["recent_videos"][0]["title"] == "Doorways"


def test_actions_are_whitelisted_and_checked(world):
    A = assistant.Action
    good_when = (T + timedelta(days=1)).isoformat()
    acts = [
        A(type="approve_video", label="Approve", video_id=world.video["id"]),
        A(type="approve_video", label="Again", video_id=world.video["id"]),          # duplicate
        A(type="pause_channel", label="Pause", channel_id="nope"),                   # unknown id
        A(type="retry_job", label="Retry", job_id=77),
        A(type="schedule_video", label="Old", video_id=world.video["id"], when="2020-01-01T00:00:00+00:00"),
        A(type="schedule_video", label="Kal", video_id=world.video["id"], when=good_when, channel_id="x"),
        A(type="pause_studio", label="Pause all", video_id=world.video["id"]),
    ]
    out = assistant.check_actions(acts)
    assert [a["type"] for a in out] == ["approve_video", "retry_job", "schedule_video", "pause_studio"]
    assert "channel_id" not in out[2]                    # stray fields are dropped
    assert "video_id" not in out[3]
    with pytest.raises(Exception):
        A(type="delete_everything", label="x")


def test_answer_saves_reply_and_buttons_without_fallback(world, monkeypatch):
    rid = _ask(world)
    _claude(world, monkeypatch, [assistant.Reply(reply="Sab theek hai. Ek video approval ka intezar kar rahi hai.",
                                                 actions=[assistant.Action(type="approve_video", label="Approve karo",
                                                                           video_id=world.video["id"])])])
    assistant.answer(rid)
    m = _msg(world, rid)
    assert m["status"] == "done" and m["content"].startswith("Sab theek")
    assert m["actions"][0]["type"] == "approve_video"
    assert world.calls_args[0]["allow_fallback"] is False


def test_limit_in_force_answers_calmly_without_calling_claude(world, monkeypatch):
    world.update("services", {"name": "anthropic"}, {"details": {"limited": True,
                                                                "resume_at": (T + timedelta(hours=2)).isoformat()}})
    rid = _ask(world)
    _claude(world, monkeypatch, [])
    assistant.answer(rid)
    assert "limit" in _msg(world, rid)["content"]
    assert world.calls["claude"] == 0


def test_limit_hit_mid_call_is_calm(world, monkeypatch):
    rid = _ask(world)
    _claude(world, monkeypatch, [LimitReached("anthropic", "limit", T + timedelta(hours=1))])
    assistant.answer(rid)
    m = _msg(world, rid)
    assert m["status"] == "done" and "wapas" in m["content"]


def test_devanagari_reply_is_asked_again(world, monkeypatch):
    rid = _ask(world)
    _claude(world, monkeypatch, [assistant.Reply(reply="सब ठीक है"), assistant.Reply(reply="Sab theek hai")])
    assistant.answer(rid)
    assert _msg(world, rid)["content"] == "Sab theek hai"


def test_history_is_trimmed(world, monkeypatch):
    for i in range(1, 251):
        world.insert("assistant_messages", {"id": i, "role": "user", "content": str(i), "status": "done"})
    world.insert("assistant_messages", {"id": 251, "role": "assistant", "content": "", "status": "pending"})
    _claude(world, monkeypatch, [assistant.Reply(reply="ok")])
    assistant.answer(251)
    ids = sorted(r["id"] for r in world.tables["assistant_messages"])
    assert len(ids) == assistant.KEEP and ids[-1] == 251


def test_structured_never_falls_back_when_asked_not_to(monkeypatch):
    monkeypatch.setattr(llm, "backend", lambda: "api")      # limit hit + fallback room
    monkeypatch.setattr(llm.settings, "get", lambda *a, **k: {})
    monkeypatch.setattr(llm, "_get_client", lambda: (_ for _ in ()).throw(AssertionError("API used")))

    def sub(*a, **k):
        raise LimitReached("anthropic", "limit", T + timedelta(hours=1))
    monkeypatch.setattr(llm, "_sub_run", sub)
    with pytest.raises(LimitReached):
        REAL_STRUCTURED(assistant.Reply, "s", "p", purpose="assistant", allow_fallback=False)
