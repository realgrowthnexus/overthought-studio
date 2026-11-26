"""Worker entrypoint: heartbeat + scheduler + two job lanes (heavy: video production, light: everything else)."""
from __future__ import annotations

import os
import platform
import shutil
import signal
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

from . import __version__, assistant, config, db, ops, pipeline, scheduler, spend
from .log import event, log
from .services import LimitReached, PermanentError, ServiceProblem, local_time, report_problem

HEAVY = ["produce_video"]
LIGHT = ["plan_channel", "research_ideas", "publish_video", "check_publish", "sync_stats", "import_stats",
         "weekly_review", "health_check", "refresh_tokens", "backup_db", "cleanup_storage", "make_thumb"]
CHAT = ["assistant_reply"]                          # own lane: the owner never waits behind a backup or a stats sync
BUDGET_GATED = {"produce_video", "plan_channel", "research_ideas", "weekly_review"}
STOP = threading.Event()


def handle(job: dict) -> dict | None:
    p = job.get("payload") or {}
    t = job["type"]
    if t == "produce_video":
        def cleared() -> None:              # a redo wipes its stage once; retries and resumes continue from there
            rest = {k: v for k, v in p.items() if k != "from_stage"}
            db.update("jobs", {"id": job["id"]}, {"payload": rest})
        return {"video": pipeline.produce(p["video_id"], p.get("from_stage"), stop_after=p.get("stop_after"),
                                          on_cleared=cleared)["id"]}
    if t == "plan_channel":
        return ops.plan_channel(p["channel_id"], bool(p.get("force")), stop_after=p.get("stop_after"))
    if t == "research_ideas":
        return ops.research_ideas(p["channel_id"], int(p.get("count", 12)))
    if t == "publish_video":
        return ops.publish_video(p["video_id"])
    if t == "check_publish":
        return ops.check_publish(p["video_id"], int(p.get("attempt", 0)))
    if t == "sync_stats":
        return ops.sync_stats(p.get("channel_id"))
    if t == "import_stats":
        return ops.import_stats(p["storage_path"], p["channel_id"])
    if t == "weekly_review":
        return ops.weekly_review(p.get("channel_id"))
    if t == "health_check":
        return ops.health_check()
    if t == "refresh_tokens":
        return ops.refresh_tokens()
    if t == "backup_db":
        return ops.backup_db()
    if t == "cleanup_storage":
        return ops.cleanup_storage()
    if t == "assistant_reply":
        return assistant.answer(int(p["reply_id"]))
    if t == "make_thumb":
        return pipeline.make_thumb(p["video_id"])
    raise RuntimeError(f"unknown job type {t}")


PRODUCTION = {"produce_video", "plan_channel"}     # only these may change a video to blocked/failed generically
MAX_WAITS = 144                                    # 144 parks ≈ 24 h of waiting on a service
_current: dict[str, int] = {}                      # lane → running job id (for the lock heartbeat)


def _finish(job: dict, **vals) -> None:
    vals.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    db.update("jobs", {"id": job["id"]}, vals)


def _cleanup_work(vid: str | None) -> None:
    if vid:
        shutil.rmtree(config.WORK / "videos" / vid, ignore_errors=True)


def run_one(job: dict) -> None:
    t0 = time.time()
    vid, cid = job.get("video_id"), job.get("channel_id")
    prod = job["type"] in PRODUCTION
    try:
        if job["type"] in BUDGET_GATED:
            why = spend.over_budget()
            if why:
                _park(job, "budget", why, "waiting", prod)
                event(why + "; production paused until tomorrow or until you raise the budget", "warn", "budget",
                      channel_id=cid)
                return
        res = handle(job)
        _finish(job, status="done", result=res or {}, last_error=None)
        log.info(f"job {job['id']} {job['type']} done in {time.time() - t0:.0f}s")
    except spend.BudgetReached as b:
        _park(job, "budget", str(b), "waiting", prod)
        event(f"{b}; production paused. Raise the cap in Settings if you want more this month", "warn", "budget",
              channel_id=cid, video_id=vid)
    except LimitReached as p:
        report_problem(p)
        why = f"Claude limit reached — resumes at {local_time(p.resume_at)}"
        _park(job, p.service, why, p.status, prod, count=False)
        event(f"Paused '{job['type']}' — {why}", "warn", "services", channel_id=cid, video_id=vid)
    except ServiceProblem as p:
        report_problem(p)
        if int(job.get("waits") or 0) >= MAX_WAITS:
            _finish(job, status="failed", last_error=f"Gave up after waiting ~24h: {p}")
            if vid and prod:
                db.update("videos", {"id": vid}, {"status": "failed", "error": f"Waited 24h for {p.service}: {p.message}"})
            event(f"'{job['type']}' gave up after 24h waiting for {p.service}", "error", "services", channel_id=cid,
                  video_id=vid)
            return
        _park(job, p.service, f"{p.service.capitalize()}: {p.message}", p.status, prod)
        event(f"Paused '{job['type']}' — {p.service}: {p.message}", "error", "services", channel_id=cid, video_id=vid)
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"job {job['id']} {job['type']} failed: {e}\n{tb}")
        attempts = int(job.get("attempts") or 1)
        permanent = isinstance(e, PermanentError)
        if not permanent and attempts < int(job.get("max_attempts") or 3):
            run_after = datetime.now(timezone.utc) + timedelta(minutes=2 ** attempts * 2)
            _finish(job, status="queued", last_error=str(e)[:2000], run_after=run_after.isoformat(), finished_at=None,
                    locked_by=None, locked_at=None)
            event(f"{job['type']} failed (attempt {attempts}), retrying: {str(e)[:300]}", "warn", "jobs",
                  channel_id=cid, video_id=vid)
        else:
            _finish(job, status="failed", last_error=str(e)[:2000])
            if vid and prod:
                db.update("videos", {"id": vid}, {"status": "failed", "error": str(e)[:1000], "stage_detail": None})
                _cleanup_work(vid)
            elif vid and job["type"] == "check_publish":
                # never mark a possibly-live video failed because a status poll errored; re-check later
                ops.enqueue("check_publish", {"video_id": vid, "attempt": int((job.get("payload") or {}).get("attempt", 0)) + 1},
                            dedupe=f"check:{vid}:late:{int(time.time()) // 3600}",
                            run_after=datetime.now(timezone.utc) + timedelta(minutes=30), channel_id=cid, video_id=vid)
            event(f"{job['type']} failed{' permanently' if not permanent else ''}: {str(e)[:400]}", "error", "jobs",
                  channel_id=cid, video_id=vid)


def _park(job: dict, service: str, reason: str, parked_status: str, prod: bool, count: bool = True) -> None:
    vid, cid = job.get("video_id"), job.get("channel_id")
    prev = None
    if vid and prod:
        v = db.select("videos", {"id": vid}, single=True, columns="status")
        prev = v["status"] if v and v["status"] != "blocked" else None
        db.update("videos", {"id": vid}, {"status": "blocked", "error": reason})
    _finish(job, status="waiting", waiting_on=service, last_error=reason, finished_at=None, locked_by=None,
            locked_at=None, waits=int(job.get("waits") or 0) + (1 if count else 0), parked_status=parked_status,
            attempts=max(0, int(job.get("attempts") or 1) - 1),    # parking is not a failed try
            prev_video_status=prev or job.get("prev_video_status"))
    if cid:
        db.update("channels", {"id": cid}, {"blocked_reason": reason + (" — raise it in Settings" if service == "budget" else "")})


def lane(name: str, types: list[str]) -> None:
    wid = f"{config.WORKER_ID}:{name}"
    while not STOP.is_set():
        try:
            rows = db.rpc("claim_job", {"p_worker": wid, "p_types": types})
            if rows:
                _current[name] = rows[0]["id"]
                try:
                    run_one(rows[0])
                finally:
                    _current.pop(name, None)
                continue
        except Exception as e:
            log.warning(f"lane {name}: {e}")
        STOP.wait(5)


def lock_heartbeat() -> None:
    """Keep locked_at fresh for running jobs so long renders are never 'recovered' by claim_job."""
    while not STOP.is_set():
        for jid in list(_current.values()):
            try:
                db.update("jobs", {"id": jid, "status": "running"}, {"locked_at": datetime.now(timezone.utc).isoformat()})
            except Exception as e:
                log.warning(f"lock heartbeat: {e}")
        STOP.wait(60)


def heartbeat_and_schedule() -> None:
    while not STOP.is_set():
        try:
            db.insert("worker_heartbeats", {"worker_id": config.WORKER_ID, "version": __version__,
                                            "host": platform.node(), "last_seen": datetime.now(timezone.utc).isoformat(),
                                            "info": {"cpus": os.cpu_count(), "render_procs": config.RENDER_PROCS,
                                                     "dry_run": config.DRY_RUN}},
                      upsert=True, on_conflict="worker_id")
            db.update("services", {"name": "worker"}, {"status": "ok", "message": f"{config.WORKER_ID} v{__version__}",
                                                       "checked_at": datetime.now(timezone.utc).isoformat()})
            scheduler.tick()
        except Exception as e:
            log.warning(f"scheduler: {e}")
        STOP.wait(60)


def reset_stale_jobs() -> None:
    """Jobs this worker was running when it last stopped go back to the queue — unless they already used all
    their attempts (a crash loop must not retry forever)."""
    for j in db.select("jobs", {"status": "running", "locked_by": ("like", f"{config.WORKER_ID}:*")}):
        try:
            if int(j.get("attempts") or 0) >= int(j.get("max_attempts") or 3):
                _finish(j, status="failed", last_error="Stopped mid-job too many times (worker restarts)")
                if j.get("video_id") and j["type"] in PRODUCTION:
                    db.update("videos", {"id": j["video_id"]}, {"status": "failed", "error": ops.ORPHAN_ERROR,
                                                                "stage_detail": None})
                continue
            db.update("jobs", {"id": j["id"]}, {"status": "queued", "locked_by": None, "locked_at": None})
        except Exception as e:                      # one bad row must not leave the others stuck as 'running'
            log.warning(f"startup reset of job {j.get('id')}: {e}")


def main() -> None:
    if not config.SUPABASE_KEY:
        log.warning("SUPABASE_SERVICE_ROLE_KEY not set (ok only behind the dev proxy)")
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    try:
        reset_stale_jobs()
    except Exception as e:
        log.warning(f"startup reset: {e}")
    event(f"Worker {config.WORKER_ID} started (v{__version__})", "info", "worker")
    lanes = [threading.Thread(target=lane, args=("heavy", HEAVY), name="heavy"),
             threading.Thread(target=lane, args=("chat", CHAT), name="chat")]
    for i in range(max(1, config.CONCURRENCY)):
        lanes.append(threading.Thread(target=lane, args=(f"light{i}", LIGHT), name=f"light{i}"))
    helpers = [threading.Thread(target=heartbeat_and_schedule, daemon=True, name="sched"),
               threading.Thread(target=lock_heartbeat, daemon=True, name="locks")]
    for th in helpers + lanes:
        th.start()
    while not STOP.is_set():
        STOP.wait(1)
    log.info("stopping: finishing running jobs (up to 15 min)…")
    deadline = time.time() + 900
    for th in lanes:
        th.join(timeout=max(1, deadline - time.time()))
    log.info("stopped")


if __name__ == "__main__":
    main()
