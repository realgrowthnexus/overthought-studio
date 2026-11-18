"""Cost ledger + budget guard."""
from datetime import datetime, timedelta, timezone

from . import db, settings


def record(service: str, amount_usd: float, *, units=None, unit=None, detail=None, channel_id=None,
           video_id=None) -> None:
    db.insert("spend", {"service": service, "amount_usd": round(float(amount_usd), 6), "units": units,
                        "unit": unit, "detail": detail, "channel_id": channel_id, "video_id": video_id})


def total_since(dt: datetime, service: str | None = None) -> float:
    v = db.rpc("spend_total", {"p_since": dt.isoformat(), "p_service": service}, idempotent=True)
    return round(float(v or 0), 4)


def budget_state() -> dict:
    s = settings.get()
    now = datetime.now(timezone.utc)
    day = total_since(now - timedelta(hours=24))
    month = total_since(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    return {"day": day, "month": month, "day_limit": float(s.get("daily_budget_usd") or 0),
            "month_limit": float(s.get("monthly_budget_usd") or 0)}


def over_budget() -> str | None:
    b = budget_state()
    if b["day_limit"] and b["day"] >= b["day_limit"]:
        return f"Daily budget reached (${b['day']:.2f} of ${b['day_limit']:.2f})"
    if b["month_limit"] and b["month"] >= b["month_limit"]:
        return f"Monthly budget reached (${b['month']:.2f} of ${b['month_limit']:.2f})"
    return None
