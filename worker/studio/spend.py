"""Cost ledger + budget guard.

RunPod has its own hard monthly cap (Settings, default $100). What counts against it is the larger of
  - our ledger (an estimate per image), and
  - the real RunPod balance drops we observe this month (top-ups are ignored),
so a wrong per-image estimate can never let real spending run past the cap.
"""
import threading
from datetime import datetime, timedelta, timezone

from . import db, settings

RUNPOD_IMAGE_RESERVE = 0.05      # per image in flight, on top of what is already spent
RUNPOD_MARGIN = 1.0              # stop this far below the cap


class BudgetReached(Exception):
    pass


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


def _month_key(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


def _month_start() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def observe_runpod_balance(balance: float) -> None:
    """Called with the real RunPod balance (health check every 10 min). Adds balance drops to this month's meter."""
    m = settings.get("runpod_meter", ttl=0)
    month = _month_key()
    used = float(m.get("used") or 0) if m.get("month") == month else 0.0
    last = m.get("last_balance")
    if last is not None and balance < float(last):
        used += float(last) - balance
    settings.put("runpod_meter", {"month": month, "used": round(used, 4), "last_balance": round(balance, 4),
                                  "seen_at": datetime.now(timezone.utc).isoformat()})


def runpod_month() -> float:
    m = settings.get("runpod_meter", ttl=0)
    observed = float(m.get("used") or 0) if m.get("month") == _month_key() else 0.0
    return round(max(total_since(_month_start(), "runpod"), observed), 4)


def runpod_cap() -> float:
    return float(settings.get().get("runpod_monthly_cap_usd") or 0)


def runpod_cap_message() -> str | None:
    cap = runpod_cap()
    if cap <= 0:
        return None
    used = runpod_month()
    if used + RUNPOD_MARGIN >= cap:
        return f"RunPod monthly cap reached (${used:.2f} of ${cap:.2f}) — images resume on the 1st"
    return None


_inflight = 0
_lock = threading.Lock()


class runpod_slot:
    """Reserve room for one image before calling RunPod; refuses when the cap would be crossed."""
    def __enter__(self):
        global _inflight
        with _lock:
            cap = runpod_cap()
            if cap > 0:
                used = runpod_month()
                if used + (_inflight + 1) * RUNPOD_IMAGE_RESERVE + RUNPOD_MARGIN > cap:
                    raise BudgetReached(f"RunPod monthly cap reached (${used:.2f} of ${cap:.2f}) — images resume on the 1st")
            _inflight += 1
        return self

    def __exit__(self, *exc):
        global _inflight
        with _lock:
            _inflight -= 1
        return False


def over_budget() -> str | None:
    rp = runpod_cap_message()
    if rp:
        return rp
    b = budget_state()
    if b["day_limit"] and b["day"] >= b["day_limit"]:
        return f"Daily budget reached (${b['day']:.2f} of ${b['day_limit']:.2f})"
    if b["month_limit"] and b["month"] >= b["month_limit"]:
        return f"Monthly budget reached (${b['month']:.2f} of ${b['month_limit']:.2f})"
    return None
