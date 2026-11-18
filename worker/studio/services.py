"""External-service status, typed failures, and the 'why did it stop' messages shown on the dashboard."""
from __future__ import annotations

from datetime import datetime, timezone

from . import db
from .log import event

FIX_HINTS = {
    "anthropic": "Top up credits at console.anthropic.com → Billing, then enter the new balance in Settings.",
    "elevenlabs": "Top up or upgrade at elevenlabs.io → Subscription. Work resumes automatically.",
    "runpod": "Add funds at runpod.io → Billing. Work resumes automatically.",
    "tiktok": "Reconnect the TikTok account in Accounts, or check the TikTok app keys in Settings.",
    "storage": "Supabase storage is full or unreachable — lower retention days or upgrade the Supabase plan.",
}


class ServiceProblem(Exception):
    """Base: a dependency prevents work. Jobs park as 'waiting' until the service is healthy."""
    status = "down"

    def __init__(self, service: str, message: str):
        super().__init__(f"{service}: {message}")
        self.service = service
        self.message = message


class OutOfCredits(ServiceProblem):
    status = "out_of_credits"


class ServiceDown(ServiceProblem):
    status = "down"


class NotConfigured(ServiceProblem):
    status = "unconfigured"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_status(name: str, status: str, message: str | None = None, *, balance=None, unit=None, limit=None,
               details: dict | None = None) -> None:
    prev = db.select("services", {"name": name}, single=True) or {}
    vals = {"status": status, "message": message, "checked_at": now_iso()}
    if balance is not None:
        vals["balance"] = balance
    if unit is not None:
        vals["balance_unit"] = unit
    if limit is not None:
        vals["balance_limit"] = limit
    if details is not None:
        vals["details"] = details
    db.update("services", {"name": name}, vals)
    if prev.get("status") != status:
        lvl = "success" if status == "ok" else ("warn" if status in ("warning", "unconfigured") else "error")
        msg = f"{name} is now {status.replace('_', ' ')}" + (f" — {message}" if message else "")
        event(msg, lvl, "services", data={"service": name, "from": prev.get("status"), "to": status})


def report_problem(p: ServiceProblem) -> None:
    hint = FIX_HINTS.get(p.service, "")
    set_status(p.service, p.status, f"{p.message}. {hint}".strip())


def is_ok(name: str) -> bool:
    row = db.select("services", {"name": name}, single=True)
    return bool(row) and row["status"] in ("ok", "warning")


def statuses() -> dict[str, dict]:
    return {r["name"]: r for r in db.select("services")}
