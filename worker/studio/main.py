"""Worker entrypoint: heartbeat + scheduler + two job lanes (heavy: video production, light: everything else)."""
from __future__ import annotations

import os
import platform
import signal
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

from . import __version__, config, db, ops, pipeline, scheduler, spend
from .log import event, log
from .services import ServiceProblem, report_problem

HEAVY = ["produce_video"]
LIGHT = ["plan_channel", "research_ideas", "publish_video", "check_publish", "sync_stats", "import_stats",
         "weekly_review", "health_check", "refresh_tokens", "backup_db", "cleanup_storage"]
BUDGET_GATED = {"produce_video", "plan_channel", "research_ideas", "weekly_review"}
STOP = threading.Event()


def handle(job: dict) -> dict | None:
    p = job.get("payload") or {}
    t = job["type"]
    if t == "produce_video":
        return {"video": pipeline.produce(p["video_id"], p.get("from_stage"))["id"]}
    if t == "plan_channel":
        return ops.plan_channel(p["channel_id"], bool(p.get("force")))
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
    raise RuntimeError(f"unknown job type {t}")


def _finish(job: dict, **vals) -> None:
    vals.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    db.update("jobs", {"id": job["id"]}, vals)


def run_one(job: dict) -> None:
    t0 = time.time()
    vid, cid = job.get("video_id"), job.get("channel_id")
    try:
        if job["type"] in BUDGET_GATED:
            why = spend.over_budget()
            if why:
                _finish(job, status="waiting", waiting_on="budget", last_error=why, finished_at=None)
                if cid:
                    db.update("channels", {"id": cid}, {"blocked_reason": why + " — raise it in Settings"})
                if vid:
                    db.update("videos", {"id": vid}, {"status": "blocked", "error": why})
                event(why + "; production paused until tomorrow or until you raise the budget", "warn", "budget",
                      channel_id=cid)
                return
        res = handle(job)
        _finish(job, status="done", result=res or {}, last_error=None)
        log.info(f"job {job['id']} {job['type']} done in {time.time() - t0:.0f}s")
    except ServiceProblem as p:
        report_problem(p)
        _finish(job, status="waiting", waiting_on=p.service, last_error=str(p), finished_at=None)
        reason = f"{p.service.capitalize()}: {p.message}"
        if cid:
            db.update("channels", {"id": cid}, {"blocked_reason": reason})
        if vid:
            db.update("videos", {"id": vid}, {"status": "blocked", "error": reason})
        event(f"Paused '{job['type']}' — {reason}", "error", "services", channel_id=cid, video_id=vid)
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"job {job['id']} {job['type']} failed: {e}\n{tb}")
        attempts = int(job.get("attempts") or 1)
        if attempts < int(job.get("max_attempts") or 3):
            run_after = datetime.now(timezone.utc) + timedelta(minutes=2 ** attempts * 2)
            _finish(job, status="queued", last_error=str(e)[:2000], run_after=run_after.isoformat(), finished_at=None,
                    locked_by=None, locked_at=None)
            event(f"{job['type']} failed (attempt {attempts}), retrying: {str(e)[:300]}", "warn", "jobs",
                  channel_id=cid, video_id=vid)
        else:
            _finish(job, status="failed", last_error=str(e)[:2000])
            if vid:
                db.update("videos", {"id": vid}, {"status": "failed", "error": str(e)[:1000], "stage_detail": None})
            event(f"{job['type']} failed permanently: {str(e)[:400]}", "error", "jobs", channel_id=cid, video_id=vid)


def lane(name: str, types: list[str]) -> None:
    wid = f"{config.WORKER_ID}:{name}"
    while not STOP.is_set():
        try:
            rows = db.rpc("claim_job", {"p_worker": wid, "p_types": types})
            if rows:
                run_one(rows[0])
                continue
        except Exception as e:
            log.warning(f"lane {name}: {e}")
        STOP.wait(5)


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


def main() -> None:
    if not config.SUPABASE_KEY:
        log.warning("SUPABASE_SERVICE_ROLE_KEY not set (ok only behind the dev proxy)")
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    event(f"Worker {config.WORKER_ID} started (v{__version__})", "info", "worker")
    threads = [threading.Thread(target=heartbeat_and_schedule, daemon=True, name="sched"),
               threading.Thread(target=lane, args=("heavy", HEAVY), daemon=True, name="heavy")]
    for i in range(max(1, config.CONCURRENCY)):
        threads.append(threading.Thread(target=lane, args=(f"light{i}", LIGHT), daemon=True, name=f"light{i}"))
    for th in threads:
        th.start()
    while not STOP.is_set():
        STOP.wait(1)
    log.info("stopping…")
    time.sleep(2)


if __name__ == "__main__":
    main()
