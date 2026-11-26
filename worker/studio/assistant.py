"""The dashboard's AI assistant: answers the owner from a live snapshot of the studio, and proposes actions as
buttons. It never changes anything itself; each button runs an admin-checked dashboard action only when the owner
clicks it. Runs on the same Claude plan (Sonnet, medium) and never on the paid API fallback."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

from . import db, llm, settings, spend
from .log import event, log
from .services import LimitReached, NotConfigured, ServiceProblem, limit_active, local_time

KEEP = 200                 # messages kept in the chat history
HISTORY = 12               # messages sent to Claude
MAX_ACTIONS = 4
SNAPSHOT_MAX = 60_000      # characters; the prompt goes through argv, keep it well under the kernel's 128 KB

ActionType = Literal["pause_channel", "resume_channel", "pause_studio", "resume_studio", "make_video",
                     "retry_job", "cancel_job", "approve_video", "reject_video", "publish_now",
                     "schedule_video", "clear_schedule"]
NEEDS = {
    "pause_channel": "channel", "resume_channel": "channel", "make_video": "channel",
    "retry_job": "job", "cancel_job": "job",
    "approve_video": "video", "reject_video": "video", "publish_now": "video", "schedule_video": "video",
    "clear_schedule": "video",
    "pause_studio": None, "resume_studio": None,
}


class Action(BaseModel):
    type: ActionType
    label: str = Field(description="Short button text in the owner's language, max 60 characters")
    channel_id: str | None = None
    video_id: str | None = None
    job_id: int | None = None
    when: str | None = Field(default=None, description="schedule_video only: ISO 8601 time with a UTC offset")


class Reply(BaseModel):
    reply: str = Field(description="The answer to the owner, plain text, short")
    actions: list[Action] = Field(default_factory=list, description="0-4 buttons the owner can click")


SYSTEM = """You are the assistant inside Overthought Studio's dashboard. You talk to the studio's owner.

THE STUDIO
- It runs 5 US TikTok channels (only some are switched on). A Python worker on the owner's VPS makes each video:
  research -> script -> light content check -> scene images on RunPod (Flux) -> free Kokoro voice on the VPS ->
  render -> ready. Claude (Sonnet, medium effort) runs on the owner's Claude plan sign-in.
- Videos must be over 60 seconds. With approval on, a finished video waits as "ready" until the owner approves it.
  Approved videos take the channel's next free post slot. A time the owner sets by hand is locked.
- Posting uses TikTok's official API. Right now it sends videos to TikTok drafts (inbox): the owner opens the
  TikTok app and taps Post. Drafts don't take a caption or cover from the studio.
- A Claude plan limit ("5-hour limit" or weekly) is a calm pause: jobs wait and resume by themselves at reset.
  The same limit is shared with this chat and the owner's own Claude chats.
- RunPod has a hard monthly cap (Settings). Jobs "waiting" are parked on a service and resume on their own.
- A channel "On hold" shows the reason in blocked_reason. "Stopped making new videos" = 3 failures in 24h; the
  owner presses Resume after fixing the cause.

HOW TO ANSWER
- Answer from the SNAPSHOT only. If something is not in it, say you can't see it. Never invent numbers or ids.
- Reply in the owner's language: Roman Urdu (Urdu written in English letters) if they write Roman Urdu, otherwise
  simple English. NEVER use Devanagari or Urdu/Arabic script. The owner is not a developer: short sentences,
  plain words, no code, no ids in the text. Times: say them in the owner's time (Pakistan, PKT) when it helps.
- Keep it short: usually 1-5 sentences or a short list.

ACTIONS (buttons)
- You can't change anything yourself. When an action would clearly help, propose it as a button in `actions`;
  it only runs if the owner clicks it. Never say an action is done.
- Only these types exist: pause_channel/resume_channel/make_video (channel_id), pause_studio/resume_studio,
  retry_job/cancel_job (job_id), approve_video/reject_video/publish_now/clear_schedule (video_id),
  schedule_video (video_id + when, a future ISO time with offset).
- Use ids exactly as they appear in the SNAPSHOT. At most 4 buttons. Label = short, in the owner's language.
- Don't propose publish_now or approve_video unless the owner asked about posting or approving."""

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


# ------------------------------------------------------------------ snapshot
def _cut(s, n: int = 300):
    return s if not isinstance(s, str) or len(s) <= n else s[:n] + "…"


def snapshot() -> dict:
    t = datetime.now(timezone.utc)
    g = settings.get(ttl=0)
    chans = db.select("channels", columns="id,slug,name,status,blocked_reason,posting_mode,posts_per_day,post_times,"
                                          "timezone,require_approval,tiktok_account_id")
    cname = {c["id"]: c["name"] for c in chans}
    services = db.select("services", columns="name,status,message,balance,balance_unit,balance_limit,details")
    active = db.select("jobs", {"status": ("in", ["running", "waiting", "queued"])},
                       columns="id,type,status,waiting_on,last_error,channel_id,video_id,run_after,attempts",
                       order="id.desc", limit=40)
    failed = db.select("jobs", {"status": "failed", "finished_at": ("gte", (t - timedelta(hours=24)).isoformat())},
                       columns="id,type,status,last_error,channel_id,video_id,finished_at", order="id.desc", limit=15)
    sched = db.select("videos", {"status": "scheduled"}, columns="id,title,channel_id,scheduled_for,schedule_locked",
                      order="scheduled_for.asc", limit=10)
    recent = db.select("videos", columns="id,title,channel_id,status,error,stage_detail,created_at,duration_s,cost_usd,"
                                         "scheduled_for,posted_at", order="created_at.desc", limit=20)
    events = db.select("events", columns="level,scope,message,created_at", order="id.desc", limit=30)
    hb = db.select("worker_heartbeats", columns="worker_id,version,last_seen", order="last_seen.desc", limit=1)

    def jobs(rows):
        return [{**{k: _cut(v) for k, v in j.items() if v is not None},
                 "channel": cname.get(j.get("channel_id"))} for j in rows]

    def vids(rows):
        return [{**{k: _cut(v, 200) for k, v in v.items() if v is not None}, "channel": cname.get(v.get("channel_id"))}
                for v in rows]

    try:
        spend_today = spend.total_since(t.replace(hour=0, minute=0, second=0, microsecond=0))
        spend_month = spend.total_since(t.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        runpod = {"used_this_month_usd": spend.runpod_month(), "monthly_cap_usd": spend.runpod_cap()}
    except Exception as e:                      # a snapshot with a hole is better than no answer
        log.warning(f"assistant snapshot spend: {e}")
        spend_today = spend_month = None
        runpod = {}
    snap = {
        "now_utc": t.isoformat(timespec="minutes"),
        "now_pakistan": t.astimezone(timezone(timedelta(hours=5))).strftime("%a %b %d, %I:%M %p PKT"),
        "studio": {"paused": bool(g.get("paused")), "auto_publish": bool(g.get("auto_publish")),
                   "daily_budget_usd": g.get("daily_budget_usd"), "monthly_budget_usd": g.get("monthly_budget_usd"),
                   "api_fallback": bool(g.get("api_fallback")), "video_retention_days": g.get("video_retention_days")},
        "worker": hb[0] if hb else None,
        "services": [{k: v for k, v in s.items() if v not in (None, {}, "")} for s in services],
        "spend_usd": {"today": spend_today, "this_month": spend_month},
        "runpod": runpod,
        "channels": [{**{k: v for k, v in c.items() if k != "tiktok_account_id"},
                      "tiktok_linked": bool(c.get("tiktok_account_id"))} for c in chans],
        "jobs_active": jobs(active),
        "jobs_failed_24h": jobs(failed),
        "next_scheduled": vids(sched),
        "recent_videos": vids(recent),
        "recent_events": [{k: _cut(v) for k, v in e.items()} for e in events],
    }
    text = json.dumps(snap, default=str)
    while len(text) > SNAPSHOT_MAX and (snap["recent_events"] or snap["recent_videos"]):
        for key in ("recent_events", "recent_videos"):
            if snap[key]:
                snap[key] = snap[key][: max(0, len(snap[key]) - 5)]
        text = json.dumps(snap, default=str)
    return snap


# ------------------------------------------------------------------ actions
def _valid(a: Action, ids: dict[str, set]) -> Action | None:
    need = NEEDS[a.type]
    a.label = (a.label or a.type.replace("_", " ")).strip()[:60]
    if need == "channel" and a.channel_id not in ids["channel"]:
        return None
    if need == "video" and a.video_id not in ids["video"]:
        return None
    if need == "job" and a.job_id not in ids["job"]:
        return None
    if a.type == "schedule_video":
        try:
            when = datetime.fromisoformat((a.when or "").replace("Z", "+00:00"))
        except ValueError:
            return None
        if when.tzinfo is None or when <= datetime.now(timezone.utc) + timedelta(minutes=2):
            return None
        a.when = when.astimezone(timezone.utc).isoformat()
    keep = {"type", "label"} | ({f"{need}_id"} if need else set()) | ({"when"} if a.type == "schedule_video" else set())
    return Action.model_validate({k: v for k, v in a.model_dump().items() if k in keep})


def check_actions(actions: list[Action]) -> list[dict]:
    """Keep only whitelisted actions whose targets really exist (the dashboard re-checks on click)."""
    want_c = {a.channel_id for a in actions if a.channel_id}
    want_v = {a.video_id for a in actions if a.video_id}
    want_j = {a.job_id for a in actions if a.job_id is not None}
    ids = {
        "channel": {r["id"] for r in db.select("channels", {"id": ("in", list(want_c))}, columns="id")} if want_c else set(),
        "video": {r["id"] for r in db.select("videos", {"id": ("in", list(want_v))}, columns="id")} if want_v else set(),
        "job": {r["id"] for r in db.select("jobs", {"id": ("in", list(want_j))}, columns="id")} if want_j else set(),
    }
    out, seen = [], set()
    for a in actions:
        v = _valid(a, ids)
        key = v and (v.type, v.channel_id, v.video_id, v.job_id)
        if v and key not in seen:
            seen.add(key)
            out.append(v.model_dump(exclude_none=True))
        if len(out) >= MAX_ACTIONS:
            break
    return out


# ------------------------------------------------------------------ the job
def _history(reply_id: int) -> list[dict]:
    rows = db.select("assistant_messages", {"id": ("lt", reply_id), "status": "done"}, columns="id,role,content",
                     order="id.desc", limit=HISTORY)
    return sorted(rows, key=lambda r: r["id"])


def _limit_reply() -> str | None:
    row = db.select("services", {"name": "anthropic"}, single=True)
    if not limit_active(row):
        return None
    ra = ((row or {}).get("details") or {}).get("resume_at")
    when = local_time(datetime.fromisoformat(ra)) + " (New York time)" if ra else "soon"
    return f"Claude ki limit abhi poori ho chuki hai, is liye main abhi jawab nahi de sakta. Claude {when} wapas aa jayega. Videos bhi tab khud se dobara chalengi."


def _save(reply_id: int, content: str, actions: list[dict] | None = None, status: str = "done") -> None:
    db.update("assistant_messages", {"id": reply_id}, {"content": content, "actions": actions or [], "status": status})


def _trim() -> None:
    ids = sorted((r["id"] for r in db.select("assistant_messages", columns="id", order="id.desc", limit=KEEP + 500)),
                 reverse=True)
    if len(ids) > KEEP:
        cutoff = ids[KEEP - 1]
        db.delete("assistant_messages", {"id": ("lt", cutoff)})


def answer(reply_id: int) -> dict:
    row = db.select("assistant_messages", {"id": reply_id}, single=True)
    if not row or row.get("status") != "pending":
        return {"skipped": "nothing to answer"}
    try:
        calm = _limit_reply()
        if calm:
            _save(reply_id, calm)
            return {"limited": True}
        hist = _history(reply_id)
        if not hist or hist[-1]["role"] != "user":
            _save(reply_id, "Mujhe aap ka sawal nahi mila. Dobara likhiye.", status="error")
            return {"skipped": "no question"}
        chat = "\n".join(f"{'OWNER' if m['role'] == 'user' else 'ASSISTANT'}: {m['content']}" for m in hist)
        prompt = (f"SNAPSHOT (live state of the studio, JSON):\n{json.dumps(snapshot(), default=str)}\n\n"
                  f"CHAT SO FAR:\n{chat}\n\nAnswer the owner's last message.")
        out = None
        for attempt in range(2):
            out, _ = llm.structured(Reply, SYSTEM, prompt, purpose="assistant", max_tokens=4000,
                                    allow_fallback=False)
            if not _DEVANAGARI.search(out.reply):
                break
            prompt += "\n\nYour last answer used Devanagari script. Write it again in Roman Urdu (English letters)."
        actions = check_actions(out.actions)
        _save(reply_id, out.reply.strip()[:4000], actions)
        return {"actions": len(actions)}
    except LimitReached as p:
        _save(reply_id, "Claude ki limit abhi poori ho chuki hai. Claude "
                        f"{local_time(p.resume_at)} (New York time) wapas aa jayega, phir dobara poochiye.")
        return {"limited": True}
    except NotConfigured:
        _save(reply_id, "Claude sign in nahi hai, is liye main jawab nahi de sakta. Settings mein Claude card dekhiye.",
              status="error")
        return {"error": "not signed in"}
    except ServiceProblem as p:
        _save(reply_id, f"Claude se abhi baat nahi ho pa rahi ({p.message}). Thori dair baad dobara poochiye.",
              status="error")
        return {"error": p.message}
    except Exception as e:
        log.exception(f"assistant: {e}")
        _save(reply_id, "Jawab banate hue kuch gadbar ho gayi. Dobara poochiye.", status="error")
        event(f"Assistant reply failed: {str(e)[:300]}", "warn", "assistant")
        return {"error": str(e)[:300]}
    finally:
        try:
            _trim()
        except Exception as e:
            log.warning(f"assistant trim: {e}")
