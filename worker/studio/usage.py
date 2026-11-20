"""Claude plan usage: the 5-hour and weekly limits, what one video costs, and when to pace.

The numbers come from the same endpoint Claude Code's own /usage screen reads. If that can't be read, the last
reading is kept and marked 'estimate' and pacing stays off: limits are then handled only by park-and-resume.
Everything is stored in services.details for 'anthropic' (the dashboard's Claude card reads it).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from . import db, secrets, settings
from .log import event, log

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
PACE_AT = 95.0                  # pace when the week is projected to pass this % of the weekly limit
SAMPLES = 5                     # per-video cost = average of the last N measured videos
_KEY = "claude_video_usage"     # settings row: {video_id: {start, end, week_reset}}
DONE = ("ready", "approved", "scheduled", "publishing", "posted")


def _http() -> httpx.Client:
    return httpx.Client(timeout=10)


def _window(raw) -> dict | None:
    if not isinstance(raw, dict) or raw.get("utilization") is None:
        return None
    return {"pct": float(raw["utilization"]), "resets_at": raw.get("resets_at")}


def read() -> dict | None:
    tok = secrets.get("claude_oauth_token")
    if not tok:
        return None
    try:
        with _http() as c:
            r = c.get(USAGE_URL, headers={"Authorization": f"Bearer {tok}", "anthropic-beta": "oauth-2025-04-20"})
        if r.status_code != 200:
            return None
        body = r.json()
        five, week = _window(body.get("five_hour")), _window(body.get("seven_day"))
    except Exception as e:
        log.info(f"claude usage not readable: {type(e).__name__}")
        return None
    if not five or not week:
        return None
    return {"five_hour": five, "seven_day": week, "source": "reported"}


def _row() -> dict:
    return db.select("services", {"name": "anthropic"}, single=True) or {}


def details() -> dict:
    return dict(_row().get("details") or {})


def _save(d: dict) -> None:
    db.update("services", {"name": "anthropic"}, {"details": d})


def reset_for_limit() -> datetime | None:
    """When a limit that was just hit lifts: the reset of whichever window is (nearly) full."""
    r = read()
    if not r:
        return None
    full = [w for w in (r["five_hour"], r["seven_day"]) if w["pct"] >= 99 and w.get("resets_at")]
    if not full:
        return None
    return max(datetime.fromisoformat(w["resets_at"]) for w in full)


# --------------------------------------------------------------- per-video cost
def _videos() -> dict:
    return dict(settings.get(_KEY, ttl=0) or {})


def before_run(video_id: str | None) -> None:
    if not video_id:
        return
    vids = _videos()
    if video_id in vids:
        return
    r = read()
    if r:
        vids[video_id] = {"start": r["seven_day"]["pct"], "week_reset": r["seven_day"].get("resets_at")}
        settings.put(_KEY, vids)


def after_run(video_id: str | None) -> None:
    if not video_id:
        return
    vids = _videos()
    m = vids.get(video_id)
    r = read()
    if not m or not r:
        return
    if r["seven_day"].get("resets_at") != m.get("week_reset"):
        vids.pop(video_id)                           # the week reset mid-video: the delta means nothing
    else:
        m["end"] = r["seven_day"]["pct"]
    settings.put(_KEY, vids)


def _per_video_pct(vids: dict) -> float | None:
    done = {v["id"]: v.get("updated_at") or "" for v in
            db.select("videos", {"id": ("in", list(vids)), "status": ("in", list(DONE))}, columns="id,updated_at")} \
        if vids else {}
    deltas = [(done[k], m["end"] - m["start"]) for k, m in vids.items()
              if k in done and m.get("end") is not None and m["end"] >= m["start"]]
    deltas.sort()
    last = [d for _, d in deltas[-SAMPLES:]]
    return round(sum(last) / len(last), 2) if last else None


# --------------------------------------------------------------- pacing
def remaining_slots(until: datetime) -> int:
    from .scheduler import slots
    n = 0
    for ch in db.select("channels", {"status": "active"}):
        days = max(0, (until - datetime.now(timezone.utc)).days + 1)
        n += sum(1 for s in slots(ch, days) if s < until)
    return n


def pacing_on() -> bool:
    d = details()
    week, per = d.get("seven_day") or {}, d.get("per_video_pct")
    if d.get("source") != "reported" or not per or week.get("pct") is None or not week.get("resets_at"):
        return False
    left = remaining_slots(datetime.fromisoformat(week["resets_at"]))
    return float(week["pct"]) + left * float(per) >= PACE_AT


def refresh() -> dict:
    """Health-check step: read the limits, update the per-video cost, flip pacing, store it all for the card."""
    d = details()
    r = read()
    if r:
        d.update(r)
    elif d.get("seven_day"):
        d["source"] = "estimate"
    vids = _videos()
    per = _per_video_pct(vids)
    if per is not None:
        d["per_video_pct"] = per
    if len(vids) > 50:                               # keep the settings row small
        settings.put(_KEY, dict(list(vids.items())[-50:]))
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    d["week_videos"] = len(db.select("videos", {"status": ("in", list(DONE)), "updated_at": ("gte", since)},
                                     columns="id"))
    _save(d)
    was = bool(d.get("pacing"))
    now_on = pacing_on()
    if now_on != was:
        d["pacing"] = now_on
        _save(d)
        event("Claude weekly limit is running low: evening videos are paused until the weekly reset"
              if now_on else "Claude weekly limit reset: evening videos are back on",
              "warn" if now_on else "success", "services")
    week = d.get("seven_day") or {}
    if per and week.get("pct") is not None:
        d["videos_left"] = max(0, int((100 - float(week["pct"])) // per))
        _save(d)
    return d
