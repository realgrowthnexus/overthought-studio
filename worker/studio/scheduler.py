"""Scheduler tick (every minute): keep each channel's buffer full, assign post slots, fire periodic jobs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import db, settings
from .log import event, log
from .ops import enqueue, now

IN_PRODUCTION = ["queued", "researching", "scripting", "fact_checking", "visuals", "voice", "rendering", "blocked"]


def slots(ch: dict, days: int) -> list[datetime]:
    tz = ZoneInfo(ch.get("timezone") or "America/New_York")
    times = sorted(ch.get("post_times") or ["12:30", "19:30"])[: max(0, int(ch.get("posts_per_day") or 0))]
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
    if g.get("paused"):
        return
    for ch in db.select("channels", {"status": "active"}):
        try:
            _channel(ch, t)
        except Exception as e:
            log.exception(f"scheduler error for {ch['slug']}: {e}")


def _channel(ch: dict, t: datetime) -> None:
    upcoming = slots(ch, int(ch.get("buffer_days") or 1))
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
    # 2) publish anything whose time has come
    for v in scheduled:
        if datetime.fromisoformat(v["scheduled_for"]) <= t:
            enqueue("publish_video", {"video_id": v["id"]}, dedupe=f"publish:{v['id']}", priority=2,
                    channel_id=ch["id"], video_id=v["id"])
    # 3) keep the production buffer full (one new video per tick at most; dedupe keeps it sequential)
    in_prod = [v for v in vids if v["status"] in IN_PRODUCTION]
    waiting_approval = [v for v in vids if v["status"] == "ready"]
    have = len(scheduled) + len(approved) + len(in_prod) + len(waiting_approval)
    if have < len(upcoming) and len(in_prod) < 2:
        if enqueue("plan_channel", {"channel_id": ch["id"]}, dedupe=f"plan:{ch['id']}", priority=5, channel_id=ch["id"]):
            log.info(f"{ch['slug']}: buffer {have}/{len(upcoming)} → planning a video")


def _periodic(t: datetime) -> None:
    k10 = t.strftime("%Y%m%d%H") + str(t.minute // 10)
    enqueue("health_check", {}, dedupe=f"health:{k10}", priority=3)
    enqueue("refresh_tokens", {}, dedupe=f"tokens:{t:%Y%m%d%H}", priority=3)
    if t.hour % 6 == 0:
        enqueue("sync_stats", {}, dedupe=f"stats:{t:%Y%m%d%H}", priority=6)
    if t.hour == 4:
        enqueue("backup_db", {}, dedupe=f"backup:{t:%Y%m%d}", priority=7)
    if t.hour == 5:
        enqueue("cleanup_storage", {}, dedupe=f"cleanup:{t:%Y%m%d}", priority=8)
    if t.weekday() == 0 and t.hour == 14:          # Monday ~9-10am ET
        enqueue("weekly_review", {}, dedupe=f"review:{t:%Y%W}", priority=6)
