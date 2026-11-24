"""The dashboard assistant: answers questions about the live studio and proposes actions the owner can click.

It runs on the owner's Claude sign-in (Sonnet, medium), never on the paid API fallback, and has no tools: it only
sees a snapshot of the studio that this module builds (no secrets). Proposed actions are checked against a
whitelist and real ids here, and again by the dashboard when the owner clicks — nothing runs without that click.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

from . import db, llm, settings, spend
from .log import event, log
from .services import LimitReached, ServiceProblem

ActionType = Literal["pause_channel", "resume_channel", "pause_studio", "resume_studio", "make_video", "retry_job",
                     "cancel_job", "approve_video", "reject_video", "publish_video", "set_post_time",
                     "clear_post_time"]
NEEDS = {"pause_channel": "channel", "resume_channel": "channel", "make_video": "channel", "retry_job": "job",
         "cancel_job": "job", "approve_video": "video", "reject_video": "video", "publish_video": "video",
         "set_post_time": "video", "clear_post_time": "video", "pause_studio": None, "resume_studio": None}


class ProposedAction(BaseModel):
    type: str = Field(description="One of: " + ", ".join(ActionType.__args__))
    label: str = Field(description="Short button text in the owner's language, e.g. 'Overthought pause karein'")
    channel_id: Optional[str] = None
    video_id: Optional[str] = None
    job_id: Optional[int | str] = None
    when_iso: Optional[str] = Field(default=None, description="For set_post_time: ISO 8601 with offset, in the future")


class AssistantReply(BaseModel):
    reply: str = Field(description="The answer, short and clear, in Roman Urdu or simple English (never Devanagari)")
    actions: list[ProposedAction] = Field(default_factory=list, description="0-3 buttons; only when they help")


SYSTEM = """You are the built-in assistant of Overthought Studio, a self-running studio that makes short TikTok videos
for the owner's channels. You know the studio's live state from the SNAPSHOT (JSON) you are given — answer from it,
never invent numbers. The owner is not a developer: answer in Roman Urdu or simple English (match their message;
NEVER Hindi/Devanagari script), short, friendly, concrete, with the next step.

How the studio works: each video goes research → script → content check (tone, TikTok rules, length) → scenes
(RunPod images) → voice (free Kokoro) → render → ready. Videos wait for the owner's approval, then post at the
channel's times (TikTok drafts until the TikTok app audit is done). Claude runs on the owner's Claude plan; when its
limit is hit, work pauses calmly and resumes by itself. RunPod has a hard monthly cap. A channel shows
"Stopped making new videos" after 3 failed videos in 24h until the owner presses Resume.

You can propose actions as buttons (the owner must click them). Only use these types, with real ids from the
SNAPSHOT: pause_channel/resume_channel/make_video (channel_id), pause_studio/resume_studio, retry_job/cancel_job
(job_id), approve_video/reject_video/publish_video/clear_post_time (video_id), set_post_time (video_id + when_iso).
Propose an action only when the owner asked for it or it clearly fixes their problem. Never claim you did something:
say "neeche button dabayein" instead. You cannot change keys, money settings, or TikTok accounts — send the owner
to the right dashboard page for those."""


def _since(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def snapshot() -> dict:
    """What the assistant may know: live, compact, and never any secret."""
    g = settings.get()
    services = [{k: s.get(k) for k in ("name", "status", "message", "balance", "balance_unit", "checked_at")}
                | {"limited": (s.get("details") or {}).get("limited"), "resume_at": (s.get("details") or {}).get("resume_at")}
                for s in db.select("services")]
    channels = [{k: c.get(k) for k in ("id", "slug", "name", "status", "blocked_reason", "posts_per_day",
                                       "posting_mode", "post_times", "timezone", "require_approval")}
                for c in db.select("channels")]
    jobs = [{k: j.get(k) for k in ("id", "type", "status", "attempts", "last_error", "waiting_on", "run_after",
                                   "video_id", "channel_id")}
            for j in db.select("jobs", {"status": ("in", ["queued", "running", "waiting", "failed"]),
                                        "created_at": ("gte", _since(48))}, order="id.desc", limit=25)]
    videos = [{k: v.get(k) for k in ("id", "channel_id", "title", "status", "error", "stage_detail", "duration_s",
                                     "cost_usd", "approval", "scheduled_for", "posted_at", "created_at")}
              for v in db.select("videos", order="created_at.desc", limit=20)]
    upcoming = sorted([{k: v.get(k) for k in ("id", "channel_id", "title", "scheduled_for", "schedule_locked")}
                       for v in db.select("videos", {"status": "scheduled"}, order="scheduled_for.asc", limit=10)],
                      key=lambda v: v.get("scheduled_for") or "")
    events = [{k: e.get(k) for k in ("level", "message", "created_at")}
              for e in db.select("events", order="created_at.desc", limit=30)]
    try:
        budget = spend.budget_state()
        runpod = {"month_used_usd": spend.runpod_month(), "month_cap_usd": spend.runpod_cap()}
    except Exception as e:                                # a snapshot must never fail on one source
        log.info(f"assistant budget snapshot: {e}")
        budget, runpod = {}, {}
    return {"now_utc": datetime.now(timezone.utc).isoformat(),
            "settings": {k: g.get(k) for k in ("paused", "auto_publish", "daily_budget_usd", "monthly_budget_usd",
                                                "runpod_monthly_cap_usd", "api_fallback")},
            "services": services, "channels": channels, "jobs": jobs, "videos": videos, "upcoming": upcoming,
            "events": events,
            "spend": budget, "runpod": runpod}


def _row(table: str, id_, cols: str) -> dict | None:
    try:
        return db.select(table, {"id": id_}, single=True, columns=cols)
    except Exception:
        return None


TITLE = {"pause_channel": "Pause channel", "resume_channel": "Resume channel", "make_video": "Make a video now for",
         "pause_studio": "Pause the whole studio", "resume_studio": "Resume the studio", "retry_job": "Retry job",
         "cancel_job": "Cancel job", "approve_video": "Approve video", "reject_video": "Reject video",
         "publish_video": "Publish video now", "set_post_time": "Set post time for", "clear_post_time": "Clear post time for"}


def validate_actions(actions: list[ProposedAction]) -> list[dict]:
    """Keep whitelisted actions that point at real rows; drop everything else."""
    out = []
    for a in actions[:10]:
        if a.type not in NEEDS:
            continue
        need = NEEDS[a.type]
        target = None
        if need == "channel" and a.channel_id:
            r = _row("channels", a.channel_id, "id,name")
            target = r and r.get("name")
        elif need == "video" and a.video_id:
            r = _row("videos", a.video_id, "id,title")
            target = r and (r.get("title") or "untitled")
        elif need == "job" and a.job_id:
            r = _row("jobs", a.job_id, "id,type")
            target = r and f"#{r['id']} ({r.get('type')})"
        if need is not None and not target:
            continue
        if a.type == "set_post_time":
            try:
                when = datetime.fromisoformat(a.when_iso or "")
                if when.tzinfo is None or when <= datetime.now(timezone.utc):
                    continue
            except (ValueError, TypeError):
                continue
        d = a.model_dump(exclude_none=True)
        # the button text the owner reads is built here from the real action and target, never from the model
        d["title"] = f"{TITLE[a.type]}: {target}" if target else TITLE[a.type]
        if a.type == "set_post_time":
            d["title"] += f" → {when:%a %d %b %H:%M %Z}".rstrip()
        out.append(d)
    return out[:3]


def _history(pending_id) -> list[dict]:
    rows = [r for r in db.select("assistant_messages", {"status": "done"}, order="id.desc", limit=40)
            if str(r["id"]) != str(pending_id)]
    rows.sort(key=lambda r: (r.get("created_at") or "", str(r["id"])))
    return rows[-12:]


def reply(message_id) -> dict:
    """Answer the owner's latest message into the pending assistant row `message_id`. The row is always finished."""
    import json
    try:
        hist = _history(message_id)
        convo = "\n".join(f"{r['role'].upper()}: {r['content']}" for r in hist) or "(no earlier messages)"
        prompt = (f"SNAPSHOT:\n{json.dumps(snapshot(), default=str)[:30000]}\n\nCONVERSATION (latest last):\n"
                  f"{convo}\n\nAnswer the owner's LAST message.")
        out, _ = llm.structured(AssistantReply, SYSTEM, prompt, purpose="assistant", max_tokens=3000,
                                allow_fallback=False)
        vals = {"content": out.reply.strip(), "actions": validate_actions(out.actions), "status": "done"}
    except LimitReached as p:
        when = p.resume_at.strftime("%H:%M UTC") if getattr(p, "resume_at", None) else "thori der baad"
        vals = {"content": f"Abhi Claude plan ka limit poora ho gaya hai, is liye main jawab nahi de sakta. "
                           f"Limit {when} par reset hoga — phir poochiye. Videos bhi tab tak ruki rahengi aur khud "
                           f"chal padengi.", "actions": [], "status": "done"}
    except ServiceProblem as p:
        vals = {"content": f"Claude abhi jawab nahi de raha ({p.message}). Thori der baad dobara poochiye.",
                "actions": [], "status": "error"}
    except Exception as e:
        log.warning(f"assistant reply failed: {e}")
        vals = {"content": "Maaf kijiye, jawab banate waqt masla aa gaya. Dobara poochiye.", "actions": [],
                "status": "error"}
    db.update("assistant_messages", {"id": message_id}, vals)
    if vals["status"] == "error":
        event("Assistant could not answer: " + vals["content"][:200], "warn", "assistant")
    return {"status": vals["status"], "actions": len(vals["actions"])}
