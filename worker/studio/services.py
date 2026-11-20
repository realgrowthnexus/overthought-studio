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


class LimitReached(ServiceProblem):
    """The Claude subscription's usage limit is used up. Not an error: work waits until the limit resets."""
    status = "limited"

    def __init__(self, service: str, message: str, resume_at: datetime):
        super().__init__(service, message)
        self.resume_at = resume_at


class PermanentError(RuntimeError):
    """A failure that retrying cannot fix (e.g. fact-check failed). The job fails immediately."""


def local_time(t: datetime) -> str:
    """'3:40 PM' in the studio's display timezone (US Eastern, like the rest of the dashboard)."""
    from zoneinfo import ZoneInfo
    return t.astimezone(ZoneInfo("America/New_York")).strftime("%a %I:%M %p").replace(" 0", " ")


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


SETUP_HINTS = {
    "anthropic": "Add your Anthropic API key in Settings → API keys.",
    "elevenlabs": "Add your ElevenLabs API key in Settings → API keys (enable the 'Text to Speech' and 'User: Read' permissions).",
    "runpod": "Add your RunPod API key in Settings → API keys.",
    "tiktok": "Add the TikTok app keys in Settings, then connect the account in Accounts.",
}


def report_problem(p: ServiceProblem) -> None:
    if isinstance(p, LimitReached):
        prev = (db.select("services", {"name": p.service}, single=True) or {}).get("details") or {}
        # stored as 'warning' + details.limited: the services.status check constraint has no 'limited' value
        set_status(p.service, "warning", f"{p.message}. Work resumes on its own at {local_time(p.resume_at)}.",
                   details={**prev, "limited": True, "resume_at": p.resume_at.isoformat()})
        return
    hint = (SETUP_HINTS if p.status == "unconfigured" else FIX_HINTS).get(p.service, "")
    set_status(p.service, p.status, f"{p.message}. {hint}".strip())


def limit_active(row: dict | None) -> bool:
    """True while a Claude usage limit is in force (details.limited with a resume time still in the future)."""
    d = (row or {}).get("details") or {}
    if not d.get("limited"):
        return False
    ra = d.get("resume_at")
    return not ra or datetime.fromisoformat(ra) > datetime.now(timezone.utc)


def is_ok(name: str) -> bool:
    row = db.select("services", {"name": name}, single=True)
    return bool(row) and row["status"] in ("ok", "warning")


def statuses() -> dict[str, dict]:
    return {r["name"]: r for r in db.select("services")}
