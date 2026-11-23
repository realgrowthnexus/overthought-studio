"""Global settings stored in `settings` (edited in the dashboard)."""
import time

from . import db

DEFAULTS = {"paused": False, "auto_publish": False, "model": "claude-opus-5-5", "effort": "high",
            "daily_budget_usd": 15, "monthly_budget_usd": 300, "video_retention_days": 7, "report_email": None}
_cache: dict[str, tuple[float, dict]] = {}


def get(key: str = "global", ttl: int = 30) -> dict:
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    row = db.select("settings", {"key": key}, single=True)
    val = dict(DEFAULTS) if key == "global" else {}
    if row:
        val.update(row["value"] or {})
    _cache[key] = (time.time(), val)
    return val


def put(key: str, value: dict) -> None:
    db.insert("settings", {"key": key, "value": value}, upsert=True, on_conflict="key")
    _cache.pop(key, None)
