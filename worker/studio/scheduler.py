"""Scheduler tick (every minute): keep each channel's buffer full, assign post slots, fire periodic jobs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import db, settings
from .log import event, log
from .ops import enqueue, now

BREAKER = "Stopped making new videos"
IN_PRODUCTION = ["queued", "researching", "scripting", "fact_checking", "visuals", "voice", "rendering", "blocked"]


def slots(ch: dict, days: int, pacing: bool = False) -> list[datetime]:
    """Post slots for the next `days` days. With pacing (Claude weekly limit running low) only the first post time
    of each day counts, so fewer videos get made; videos that already have a slot keep it."""
    tz = ZoneInfo(ch.get("timezone") or "America/New_York")
    times = sorted(ch.get("post_times") or ["12:30", "19:30"])[: max(0, int(ch.get("posts_per_day") or 0))]
    if pacing:
        times = times[:1]
    out = []
    local_now = datetime.now(tz)
    for d in range(days + 1):
        day = (local_now + timedelta(days=d)).date()
        for t in times:
            hh, mm = (int(x) for x in t.split(":"))
            dt = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
            if dt > local_now + timedelta(minutes=20):
                out.append(dt.astimezone(timezone.utc))
    return out


def tick() -> None:
    g = settings.get()
    t = now()
    _periodic(t)
    try:
        from .ops import sweep_stuck_videos
        sweep_stuck_videos(t)
    except Exception as e:
        log.warning(f"sweep: {e}")
    if g.get("paused"):
        return
    try:
        from . import usage
        pacing = usage.pacing_on()
    except Exception as e:
        log.warning(f"pacing check: {e}")
        pacing = False
    chans = db.select("channels", {"status": "active"})
    floor = _round_robin_floor(chans, pacing)
    for ch in chans:
        try:
            _channel(ch, t, pacing=pacing, floor=floor)
        except Exception as e:
            log.exception(f"scheduler error for {ch['slug']}: {e}")


def _buffer(ch: dict, pacing: bool) -> tuple[int, int, int]:
    """(videos held, slots to fill, videos in production) for one channel."""
    upcoming = slots(ch, int(ch.get("buffer_days") or 1), pacing=pacing)
    vids = db.select("videos", {"channel_id": ch["id"],
                                "status": ("in", IN_PRODUCTION + ["ready", "approved", "scheduled"])}, columns="status")
    in_prod = sum(1 for v in vids if v["status"] in IN_PRODUCTION)
    return len(vids), len(upcoming), in_prod


def _round_robin_floor(chans: list[dict], pacing: bool) -> int | None:
    """Fewest videos in production among channels that still need one: no channel gets a second video in
    production while another still has none (morning videos for every channel come first)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    stuck = {j["channel_id"] for j in db.select("jobs", {"type": "plan_channel", "status": "failed",
                                                          "finished_at": ("gte", since)}, columns="channel_id")}
    # only channels that can actually get a new video count: not stopped, and planning not failing right now
    able = [ch for ch in chans if not ch.get("blocked_reason") and ch["id"] not in stuck]
    short = [b for b in (_buffer(ch, pacing) for ch in able) if b[0] < b[1]]
    return min((b[2] for b in short), default=None)


def _channel(ch: dict, t: datetime, pacing: bool = False, floor: int | None = None) -> None:
    upcoming = slots(ch, int(ch.get("buffer_days") or 1), pacing=pacing)
    vids = db.select("videos", {"channel_id": ch["id"],
                                "status": ("in", IN_PRODUCTION + ["ready", "approved", "scheduled"])})
    scheduled = sorted([v for v in vids if v["status"] == "scheduled" and v.get("scheduled_for")],
                       key=lambda v: v["scheduled_for"])
    taken = {v["scheduled_for"][:16] for v in scheduled}
    # 1) give approved videos the earliest free slot
    approved = sorted([v for v in vids if v["status"] == "approved"], key=lambda v: v["created_at"])
    free = [s for s in upcoming if s.isoformat()[:16] not in taken]
    for v, s in zip(approved, free):
        db.update("videos", {"id": v["id"]}, {"status": "scheduled", "scheduled_for": s.isoformat(),
                                              "stage_detail": f"Scheduled for {s.astimezone(ZoneInfo(ch['timezone'])):%a %b %d, %I:%M %p} ET"})
        taken.add(s.isoformat()[:16])
    # 2) publish whose time has come — at most ONE per channel per tick (no burst after downtime)
    due = [v for v in scheduled if datetime.fromisoformat(v["scheduled_for"]) <= t]
    if due:
        v = due[0]
        enqueue("publish_video", {"video_id": v["id"]}, dedupe=f"publish:{v['id']}", priority=2,
                channel_id=ch["id"], video_id=v["id"])
        later = [s for s in upcoming if s.isoformat()[:16] not in taken]
        for v2, slot in zip(due[1:], later):          # overdue extras move to the next free slots
            db.update("videos", {"id": v2["id"]}, {"scheduled_for": slot.isoformat()})
            taken.add(slot.isoformat()[:16])
    # 3) circuit breaker: 3 production failures in 24h → stop planning for this channel. Only pressing Start/Resume
    #    (which writes failures_forgiven_at) forgives earlier failures; other row updates never do.
    since_dt = t - timedelta(hours=24)
    if ch.get("failures_forgiven_at"):
        since_dt = max(since_dt, datetime.fromisoformat(ch["failures_forgiven_at"]))
    fails = db.select("videos", {"channel_id": ch["id"], "status": "failed", "updated_at": ("gte", since_dt.isoformat())},
                      columns="id,error", limit=10)
    tripped = (ch.get("blocked_reason") or "").startswith(BREAKER)
    if len(fails) >= 3:
        if not tripped:
            msg = (f"{BREAKER}: {len(fails)} failed in the last 24h (last error: "
                   f"{(fails[0].get('error') or '')[:160]}). Fix the cause, then press Resume.")
            db.update("channels", {"id": ch["id"]}, {"blocked_reason": msg})
            event(msg, "error", "planner", channel_id=ch["id"])
        return
    if tripped:
        db.update("channels", {"id": ch["id"]}, {"blocked_reason": None})
        event("Planning resumed: recent failures are older than 24h or were forgiven", "success", "planner",
              channel_id=ch["id"])
    # 4) keep the production buffer full (one new video per tick at most; dedupe keeps it sequential)
    in_prod = [v for v in vids if v["status"] in IN_PRODUCTION]
    waiting_approval = [v for v in vids if v["status"] == "ready"]
    have = len(scheduled) + len(approved) + len(in_prod) + len(waiting_approval)
    if have < len(upcoming) and len(in_prod) < 2 and (floor is None or len(in_prod) <= floor):
        if not db.select("ideas", {"channel_id": ch["id"], "status": "new"}, columns="id", limit=1):
            # nothing to plan from: research ideas (at most once per 6h) instead of a failing plan job every minute
            enqueue("research_ideas", {"channel_id": ch["id"]}, once=f"research:{ch['id']}:{t:%Y%m%d}:{t.hour // 6}",
                    channel_id=ch["id"], priority=6)
            return
        if enqueue("plan_channel", {"channel_id": ch["id"]}, dedupe=f"plan:{ch['id']}", priority=5, channel_id=ch["id"]):
            log.info(f"{ch['slug']}: buffer {have}/{len(upcoming)} → planning a video")


def _periodic(t: datetime) -> None:
    # once-keys are unique across ALL job statuses → each runs exactly once per period
    k10 = t.strftime("%Y%m%d%H") + str(t.minute // 10)
    enqueue("health_check", {}, once=f"health:{k10}", priority=3)
    enqueue("refresh_tokens", {}, once=f"tokens:{t:%Y%m%d%H}", priority=3)
    enqueue("sync_stats", {}, once=f"stats:{t:%Y%m%d}:{t.hour // 6}", priority=6)
    if t.hour >= 4:
        enqueue("backup_db", {}, once=f"backup:{t:%Y%m%d}", priority=7)
    if t.hour >= 5:
        enqueue("cleanup_storage", {}, once=f"cleanup:{t:%Y%m%d}", priority=8)
    if t.weekday() == 0 and t.hour >= 14:          # Monday from ~9-10am ET
        enqueue("weekly_review", {}, once=f"review:{t:%G%V}", priority=6)
