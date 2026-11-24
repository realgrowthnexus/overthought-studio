"""Operational jobs: planning, publishing, stats, health/credits, weekly review, backups, cleanup."""
from __future__ import annotations

import csv
import gzip
import io
import json
import statistics
from datetime import date, datetime, timedelta, timezone

import httpx
from pydantic import BaseModel, Field

from . import config, content, db, llm, secrets, settings, spend, tiktok, voice
from .log import event, log
from .services import NotConfigured, OutOfCredits, PermanentError, ServiceDown, ServiceProblem, set_status


def now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(type_: str, payload: dict | None = None, *, dedupe: str | None = None, once: str | None = None,
            priority: int = 5, channel_id=None, video_id=None, run_after: datetime | None = None) -> bool:
    """dedupe: at most one *active* job with this key. once: at most one job with this key EVER (periodic jobs)."""
    row = {"type": type_, "payload": payload or {}, "priority": priority, "dedupe_key": dedupe, "once_key": once,
           "channel_id": channel_id, "video_id": video_id}
    if run_after:
        row["run_after"] = run_after.isoformat()
    try:
        db.insert("jobs", row)
        return True
    except db.DBError as e:
        if "duplicate key" in str(e) or "23505" in str(e):
            return False
        raise


# ------------------------------------------------------------------ planning
def plan_channel(channel_id: str, force: bool = False, stop_after: str | None = None) -> dict:
    ch = db.select("channels", {"id": channel_id}, single=True)
    if not ch:
        raise PermanentError("channel not found")
    if ch["status"] != "active" and not force:
        return {"skipped": "channel paused"}
    ideas = db.select("ideas", {"channel_id": channel_id, "status": "new"}, order="score.desc", limit=50)
    if len(ideas) < 10:
        # at most one idea-research run per channel per 6 hours
        enqueue("research_ideas", {"channel_id": channel_id}, once=f"research:{channel_id}:{now():%Y%m%d}:{now().hour // 6}",
                channel_id=channel_id, priority=6)
    if not ideas:
        raise PermanentError("The idea bank is empty — new ideas are being researched; planning resumes automatically")
    pw = (ch.get("strategy") or {}).get("pillar_weights") or {}
    for best in sorted(ideas, key=lambda i: -float(i["score"]) * (0.7 + 0.3 * float(pw.get(i.get("pillar") or "", 1.0)))):
        try:   # unique index (one active video per idea) makes this idempotent on retries
            v = db.insert("videos", {"channel_id": channel_id, "idea_id": best["id"], "title": best["title"],
                                     "status": "queued", "stage_detail": "Waiting for the production line"})[0]
        except db.DBError as e:
            if "23505" in str(e) or "duplicate key" in str(e):
                db.update("ideas", {"id": best["id"]}, {"status": "queued"})
                continue
            raise
        db.update("ideas", {"id": best["id"]}, {"status": "queued"})
        payload = {"video_id": v["id"], **({"stop_after": stop_after} if stop_after else {})}
        enqueue("produce_video", payload, dedupe=f"produce:{v['id']}", channel_id=channel_id,
                video_id=v["id"], priority=4)
        event(f"Planned a new video: {best['title']}", "info", "planner", channel_id=channel_id, video_id=v["id"])
        return {"video_id": v["id"], "idea": best["title"]}
    raise PermanentError("Every available idea already has a video in progress")


def release_idea(video_id: str, failed: bool) -> None:
    """A video that didn't make it gives its idea back to the bank; after 2 failed videos the idea is retired."""
    v = db.select("videos", {"id": video_id}, single=True, columns="idea_id")
    if not v or not v.get("idea_id"):
        return
    idea = db.select("ideas", {"id": v["idea_id"]}, single=True)
    if not idea:
        return
    if not failed:
        db.update("ideas", {"id": idea["id"]}, {"status": "new"})
        return
    n = int(idea.get("fail_count") or 0) + 1
    db.update("ideas", {"id": idea["id"]}, {"fail_count": n, "status": "retired" if n >= 2 else "new"})


_SWEEP = ["queued", "researching", "scripting", "fact_checking", "visuals", "voice", "rendering"]
ORPHAN_ERROR = "Production stopped unexpectedly (the worker restarted mid-job). Press Make again."


RELEASE_AFTER = timedelta(hours=6)


def release_failed_ideas(t: datetime) -> int:
    """Ideas of videos that failed > 6h ago go back to the bank (retired after 2 failures). Waiting first leaves
    the owner time to press "Make again" on the failed video without the planner grabbing the same idea."""
    old = db.select("videos", {"status": "failed", "updated_at": ("lt", (t - RELEASE_AFTER).isoformat()),
                               "idea_id": ("not.is", "null")}, columns="id,idea_id", limit=200)
    done = 0
    for v in old:
        idea = db.select("ideas", {"id": v["idea_id"], "status": "queued"}, single=True)
        if not idea:
            continue                                # already back in the bank, retired or used
        active = db.select("videos", {"idea_id": v["idea_id"], "status": ("not.in", ["failed", "rejected"])},
                           columns="id", limit=1)
        if active:
            continue                                # a redo or a new video is using it
        n = int(idea.get("fail_count") or 0) + 1
        db.update("ideas", {"id": idea["id"], "status": "queued"},
                  {"fail_count": n, "status": "retired" if n >= 2 else "new"})
        done += 1
    return done


def sweep_stuck_videos(t: datetime) -> int:
    """Videos left in a production status with no live job (worker killed) are failed, so they stop blocking
    the channel's production slots."""
    cutoff = (t - timedelta(minutes=15)).isoformat()
    # jobs first: a job that finishes after this read leaves its video out of _SWEEP, and the guarded update skips it
    live = {j["video_id"] for j in db.select("jobs", {"type": "produce_video",
                                                       "status": ("in", ["queued", "running", "waiting"])},
                                              columns="video_id")}
    stale = db.select("videos", {"status": ("in", _SWEEP), "updated_at": ("lt", cutoff)}, columns="id,channel_id,title")
    n = 0
    for v in stale:
        if v["id"] in live:
            continue
        rows = db.update("videos", {"id": v["id"], "status": ("in", _SWEEP), "updated_at": ("lt", cutoff)},
                         {"status": "failed", "error": ORPHAN_ERROR, "stage_detail": None})
        if not rows:
            continue
        event(f"{v.get('title') or 'Video'}: {ORPHAN_ERROR}", "error", "jobs", channel_id=v["channel_id"],
              video_id=v["id"])
        n += 1
    return n


def research_ideas(channel_id: str, count: int = 12) -> dict:
    ch = db.select("channels", {"id": channel_id}, single=True)
    existing = [r["title"] for r in db.select("ideas", {"channel_id": channel_id}, columns="title", limit=1000)]
    ideas, usd = content.generate_ideas(ch, existing, count)
    pw = (ch.get("strategy") or {}).get("pillar_weights") or {}
    rows = [{"channel_id": channel_id, "title": i.title, "pillar": i.pillar, "angle": i.angle, "hook": i.hook,
             "summary": i.summary, "keywords": i.keywords, "sources": [{"study": i.key_study}],
             "scores": {"interest": i.interest, "search_demand": i.search_demand, "novelty": i.novelty,
                        "evidence": i.evidence_strength}, "score": content.idea_score(i, pw), "origin": "research"}
            for i in ideas if i.title.lower() not in {e.lower() for e in existing}]
    if rows:
        db.insert("ideas", rows)
    event(f"Added {len(rows)} researched ideas (${usd:.2f})", "success", "research", channel_id=channel_id)
    return {"added": len(rows)}


# ------------------------------------------------------------------ publishing
PUBLISHABLE = ["approved", "scheduled", "ready"]


def publish_video(video_id: str) -> dict:
    v = db.select("videos", {"id": video_id}, single=True)
    ch = db.select("channels", {"id": v["channel_id"]}, single=True)
    if v["status"] in ("posted", "sent_to_drafts"):
        return {"skipped": v["status"]}
    if v["status"] == "uploading":
        if v.get("tiktok_publish_id"):            # upload finished earlier; just keep polling
            enqueue("check_publish", {"video_id": video_id}, dedupe=f"check:{video_id}", channel_id=ch["id"],
                    video_id=video_id)
            return {"resumed_check": True}
        stale = datetime.fromisoformat(v["updated_at"]) < now() - timedelta(minutes=30)
        if not stale:
            return {"skipped": "upload in progress"}
        db.update("videos", {"id": video_id, "status": "uploading"}, {"status": "approved"})   # stale, never reached TikTok
        v["status"] = "approved"
    if v["status"] not in PUBLISHABLE:
        raise PermanentError(f"Video is '{v['status']}', not ready to publish")
    if v["status"] == "ready" and ch.get("require_approval", True) and v.get("approval") != "approved":
        raise PermanentError("Video needs approval before publishing")
    if not ch.get("tiktok_account_id"):
        raise NotConfigured("tiktok", f"Channel '{ch['name']}' has no TikTok account connected")
    g = settings.get()
    mode = ch.get("posting_mode", "draft")
    if mode == "public" and not g.get("auto_publish"):
        mode = "private"            # master switch off → never public
    caption = (v.get("caption") or v["title"]).strip()
    tags = " ".join(v.get("hashtags") or [])
    title = f"{caption}\n\n{tags}".strip()
    prev = v["status"]
    # atomic claim: only one lane can move this video into 'uploading'
    claimed = db.update("videos", {"id": video_id, "status": ("in", PUBLISHABLE)},
                        {"status": "uploading", "stage_detail": f"Uploading to TikTok ({mode})", "error": None})
    if not claimed:
        return {"skipped": "already claimed"}
    pid = None
    try:
        from . import pipeline
        data = pipeline.final_video(v, ch)
        pid = tiktok.post_video(ch["tiktok_account_id"], data, mode=mode, title=title, aigc=True)
        db.update("videos", {"id": video_id}, {"tiktok_publish_id": pid, "stage_detail": "TikTok is processing the upload",
                                               "publish_status": {"mode": mode}})
    except tiktok.TikTokError as e:
        db.update("videos", {"id": video_id}, {"status": prev, "error": str(e), "stage_detail": None})
        if e.code in ("access_token_invalid", "scope_not_authorized", "invalid_grant", "invalid_token", "refresh_failed"):
            raise NotConfigured("tiktok", f"TikTok rejected the account token ({e.code}) — reconnect it in Accounts")
        if e.code in ("spam_risk_too_many_posts", "spam_risk_too_many_pending_share", "reached_active_user_cap",
                      "rate_limit_exceeded"):
            enqueue("publish_video", {"video_id": video_id}, dedupe=f"publish:{video_id}",
                    run_after=now() + timedelta(hours=3), channel_id=ch["id"], video_id=video_id)
            event(f"TikTok limit hit ({e.code}); retrying in 3h", "warn", "publish", channel_id=ch["id"], video_id=video_id)
            return {"retry": e.code}
        raise
    except BaseException:
        if pid is None:          # nothing reached TikTok → safe to try again later
            db.update("videos", {"id": video_id}, {"status": prev, "stage_detail": None})
        raise
    enqueue("check_publish", {"video_id": video_id}, dedupe=f"check:{video_id}", run_after=now() + timedelta(seconds=45),
            channel_id=ch["id"], video_id=video_id)
    event(f"Uploaded to TikTok as {mode}: {v['title']}", "success", "publish", channel_id=ch["id"], video_id=video_id)
    return {"publish_id": pid, "mode": mode}


def check_publish(video_id: str, attempt: int = 0) -> dict:
    v = db.select("videos", {"id": video_id}, single=True)
    ch = db.select("channels", {"id": v["channel_id"]}, single=True)
    if config.DRY_RUN or v.get("tiktok_publish_id") == "dry-run":
        db.update("videos", {"id": video_id}, {"status": "posted", "posted_at": now().isoformat(), "stage_detail": None})
        return {"dry_run": True}
    st = tiktok.publish_status(ch["tiktok_account_id"], v["tiktok_publish_id"])
    s = st.get("status")
    mode = (v.get("publish_status") or {}).get("mode", "draft")
    vals = {"publish_status": {**st, "mode": mode}}
    if s == "SEND_TO_USER_INBOX":
        vals.update(status="sent_to_drafts", stage_detail="In your TikTok inbox — open TikTok and tap Post",
                    posted_at=now().isoformat())
    elif s == "PUBLISH_COMPLETE":
        ids = st.get("publicaly_available_post_id") or []
        vals.update(status="posted", posted_at=now().isoformat(), stage_detail=None)
        if ids:
            vals["tiktok_video_id"] = str(ids[0])
    elif s == "FAILED":
        vals.update(status="failed", error=f"TikTok: {st.get('fail_reason')}")
        event(f"TikTok publish failed: {st.get('fail_reason')}", "error", "publish", channel_id=ch["id"], video_id=video_id)
    else:
        if attempt < 40:
            enqueue("check_publish", {"video_id": video_id, "attempt": attempt + 1}, dedupe=f"check:{video_id}:{attempt + 1}",
                    run_after=now() + timedelta(seconds=min(600, 30 * (attempt + 1))), channel_id=ch["id"],
                    video_id=video_id)
        else:
            vals.update(status="failed", error=f"TikTok still processing after many checks (last status {s}). "
                                               "Check the TikTok app; it may have posted.")
            event("Gave up waiting for TikTok processing status", "error", "publish", channel_id=ch["id"], video_id=video_id)
    if s == "PUBLISH_COMPLETE" and mode == "public" and not vals.get("tiktok_video_id") and attempt < 40:
        enqueue("check_publish", {"video_id": video_id, "attempt": attempt + 1}, dedupe=f"check:{video_id}:{attempt + 1}",
                run_after=now() + timedelta(minutes=5), channel_id=ch["id"], video_id=video_id)
    db.update("videos", {"id": video_id}, vals)
    if vals.get("status") in ("posted", "sent_to_drafts") and v.get("idea_id"):
        db.update("ideas", {"id": v["idea_id"]}, {"status": "used"})
    return st


# ------------------------------------------------------------------ stats
def sync_stats(channel_id: str | None = None) -> dict:
    where = {"tiktok_account_id": ("not.is", "null")}
    if channel_id:
        where["id"] = channel_id
    chans = db.select("channels", where)
    n = 0
    for ch in chans:
        acc_id = ch["tiktok_account_id"]
        try:
            u = tiktok.user_info(acc_id)
            db.update("tiktok_accounts", {"id": acc_id}, {k: u.get(k) for k in (
                "display_name", "username", "avatar_url", "follower_count", "following_count", "likes_count",
                "video_count", "is_verified")} | {"last_synced_at": now().isoformat()})
            db.insert("account_stats", {"tiktok_account_id": acc_id, "follower_count": u.get("follower_count"),
                                        "likes_count": u.get("likes_count"), "video_count": u.get("video_count")})
            vids = tiktok.list_videos(acc_id)
        except tiktok.TikTokError as e:
            event(f"Stats sync failed for {ch['name']}: {e}", "warn", "stats", channel_id=ch["id"])
            continue
        ours = db.select("videos", {"channel_id": ch["id"], "status": ("in", ["posted", "sent_to_drafts"])})
        by_id = {v["tiktok_video_id"]: v for v in ours if v.get("tiktok_video_id")}
        unmatched = sorted([v for v in ours if not v.get("tiktok_video_id")], key=lambda v: v.get("posted_at") or "")
        for tv in sorted(vids, key=lambda x: x.get("create_time", 0)):
            v = by_id.get(str(tv["id"]))
            if v is None and unmatched:
                # drafts published from the inbox: match by publish time and duration
                ct = datetime.fromtimestamp(tv.get("create_time", 0), timezone.utc)
                for cand in unmatched:
                    pa = datetime.fromisoformat(cand["posted_at"]) if cand.get("posted_at") else None
                    dur_ok = not cand.get("duration_s") or abs(float(cand["duration_s"]) - float(tv.get("duration") or 0)) <= 2
                    if pa and timedelta(minutes=-10) <= ct - pa <= timedelta(days=4) and dur_ok:
                        v = cand
                        unmatched.remove(cand)
                        db.update("videos", {"id": v["id"]}, {"tiktok_video_id": str(tv["id"]), "status": "posted",
                                                              "tiktok_url": tv.get("share_url"), "posted_at": ct.isoformat()})
                        break
            if v is None:
                continue
            db.insert("video_stats", {"video_id": v["id"], "views": tv.get("view_count"), "likes": tv.get("like_count"),
                                      "comments": tv.get("comment_count"), "shares": tv.get("share_count"),
                                      "raw": tv, "source": "api"})
            if tv.get("share_url") and not v.get("tiktok_url"):
                db.update("videos", {"id": v["id"]}, {"tiktok_url": tv["share_url"]})
            n += 1
    return {"videos_updated": n}


def import_stats(storage_path: str, channel_id: str) -> dict:
    """TikTok Studio export (CSV or XLSX). Matches rows to our videos by video id or caption prefix."""
    data = db.download("videos", storage_path)
    if storage_path.lower().endswith(".xlsx") or data[:2] == b"PK":
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        it = ws.iter_rows(values_only=True)
        header = [str(h or "").strip() for h in next(it, [])]
        rows = [{header[i]: ("" if v is None else str(v)) for i, v in enumerate(r) if i < len(header)} for r in it]
    else:
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
    ours = db.select("videos", {"channel_id": channel_id, "status": ("in", ["posted", "sent_to_drafts"])})

    def pick(r: dict, *names) -> str | None:
        for k, val in r.items():
            kk = (k or "").strip().lower()
            if any(n in kk for n in names):
                return val
        return None

    def num(x) -> float | None:
        if x in (None, ""):
            return None
        x = str(x).replace(",", "").replace("%", "").strip()
        try:
            return float(x)
        except ValueError:
            return None

    n = 0
    for r in rows:
        title = (pick(r, "title", "caption", "description") or "").strip().lower()
        vid = pick(r, "video id", "post id")
        match = next((v for v in ours if vid and v.get("tiktok_video_id") == str(vid).strip()), None) or \
            next((v for v in ours if title and (v.get("caption") or v["title"]).strip().lower()[:40] in title), None)
        if not match:
            continue
        comp = num(pick(r, "watched full", "full video", "completion"))
        db.insert("video_stats", {"video_id": match["id"], "source": "import",
                                  "views": num(pick(r, "views", "video views")), "likes": num(pick(r, "likes")),
                                  "comments": num(pick(r, "comments")), "shares": num(pick(r, "shares")),
                                  "saves": num(pick(r, "saves", "favorites")),
                                  "avg_watch_s": num(pick(r, "average watch", "avg. watch", "avg watch")),
                                  "completion_rate": comp / 100 if comp and comp > 1 else comp,
                                  "follows": num(pick(r, "new followers", "follows")), "raw": r})
        n += 1
    event(f"Imported TikTok Studio stats for {n} videos", "success", "stats", channel_id=channel_id)
    return {"matched": n, "rows": len(rows)}


# ------------------------------------------------------------------ weekly review
class Adjust(BaseModel):
    summary_md: str = Field(description="Weekly report in markdown: what worked, what didn't, numbers, decisions")
    pillar_weights: dict[str, float]
    hook_weights: dict[str, float]
    test_variable: str = Field(description="ONE variable to test next week: hook | length | music | topic_type | cta")
    test_variant: str
    notes_for_writer: str = Field(description="Concrete guidance the scriptwriter will read next week")
    retire_idea_titles: list[str]
    new_idea_directions: list[str]


def _latest_stats(video_ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(video_ids), 80):
        rows = db.select("video_stats", {"video_id": ("in", video_ids[i:i + 80])}, order="captured_at.desc")
        for r in rows:
            cur = out.setdefault(r["video_id"], {})
            for k in ("views", "likes", "comments", "shares", "saves", "avg_watch_s", "completion_rate", "follows"):
                if cur.get(k) is None and r.get(k) is not None:
                    cur[k] = r[k]
    return out


def weekly_review(channel_id: str | None = None) -> dict:
    chans = [db.select("channels", {"id": channel_id}, single=True)] if channel_id else db.select("channels")
    done = []
    for ch in chans:
        since = (now() - timedelta(days=28)).isoformat()
        vids = db.select("videos", {"channel_id": ch["id"], "posted_at": ("gte", since)})
        if len(vids) < 3:
            continue
        stats = _latest_stats([v["id"] for v in vids])
        table = []
        for v in vids:
            s = stats.get(v["id"], {})
            views = float(s.get("views") or 0)
            table.append({"title": v["title"], "posted": v["posted_at"], "seconds": v.get("duration_s"),
                          "hook_style": (v.get("experiment") or {}).get("hook_style"),
                          "pillar": None, "views": views,
                          "share_rate": round(float(s.get("shares") or 0) / views, 4) if views else None,
                          "like_rate": round(float(s.get("likes") or 0) / views, 4) if views else None,
                          "comment_rate": round(float(s.get("comments") or 0) / views, 4) if views else None,
                          "completion": s.get("completion_rate"), "avg_watch_s": s.get("avg_watch_s")})
        med = statistics.median([t["views"] for t in table]) if table else 0
        prompt = f"""Weekly performance review for TikTok channel "{ch['name']}" ({ch['niche']}).
Channel median views (28d): {med}
Current strategy: {json.dumps(ch.get('strategy') or {})}
Pillars: {json.dumps((ch.get('content') or {}).get('pillars'))}
Hook styles: {json.dumps((ch.get('content') or {}).get('hook_styles'))}
Videos (last 28 days):
{json.dumps(table, default=str)[:20000]}

Rules: double down on topics/hook styles that beat the median on completion and shares; retire what underperforms;
change only ONE test variable for next week; be specific; weights between 0.2 and 2.0."""
        adj, usd = llm.structured(Adjust, content.channel_system(ch), prompt, purpose="weekly_review",
                                  channel_id=ch["id"], max_tokens=12000)
        strategy = {"week_of": date.today().isoformat(), "pillar_weights": adj.pillar_weights,
                    "hook_weights": adj.hook_weights, "test": {"variable": adj.test_variable, "variant": adj.test_variant},
                    "notes": adj.notes_for_writer, "directions": adj.new_idea_directions}
        db.update("channels", {"id": ch["id"]}, {"strategy": strategy})
        for t in adj.retire_idea_titles:
            db.update("ideas", {"channel_id": ch["id"], "title": t, "status": "new"}, {"status": "retired"})
        db.insert("reports", {"channel_id": ch["id"], "period_start": (date.today() - timedelta(days=7)).isoformat(),
                              "period_end": date.today().isoformat(), "title": f"{ch['name']} — week of {date.today():%b %d}",
                              "summary_md": adj.summary_md, "data": {"median_views": med, "videos": table},
                              "changes": [{"strategy": strategy}, {"retired": adj.retire_idea_titles}]})
        event(f"Weekly review done for {ch['name']}: testing {adj.test_variable} → {adj.test_variant}", "success",
              "review", channel_id=ch["id"])
        _email_report(ch, adj.summary_md)
        done.append(ch["name"])
    return {"reviewed": done}


def _email_report(ch: dict, md: str) -> None:
    to = settings.get().get("report_email")
    key = secrets.get("resend_api_key")
    if not to or not key:
        return
    try:
        httpx.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {key}"}, timeout=30,
                   json={"from": "Overthought Studio <reports@resend.dev>", "to": [to],
                         "subject": f"Weekly report — {ch['name']}", "text": md})
    except Exception as e:
        log.warning(f"report email failed: {e}")


# ------------------------------------------------------------------ health & credits
def _section(name: str, fn, out: dict) -> None:
    """Run one health section; never let it break the others or the resume step."""
    try:
        out[name] = fn()
    except ServiceProblem as p:
        _keep_or_report(p)
        out[name] = p.status
    except Exception as e:
        log.warning(f"health {name}: {e}")
        set_status(name, "warning", f"Health check could not complete: {_scrub(str(e))[:140]}")
        out[name] = "warning"


def _scrub(text: str) -> str:
    import re
    return re.sub(r"(api_key|key|token|secret)=[^&\s]+", r"\1=***", text)


def _health_anthropic() -> str:
    if llm.backend() == "subscription":
        return _health_claude_subscription()
    llm.ping()
    credit = settings.get("anthropic_credit")
    bal, set_at = credit.get("balance_usd"), credit.get("set_at")
    if bal is not None and set_at:
        used = spend.total_since(datetime.fromisoformat(set_at), "anthropic")
        left = float(bal) - used
        st = "ok" if left > 5 else ("warning" if left > 0.5 else "out_of_credits")
        set_status("anthropic", st, None if st == "ok" else f"Estimated ${left:.2f} left. Top up at console.anthropic.com",
                   balance=round(left, 2), unit="usd", limit=float(bal))
        return st
    set_status("anthropic", "ok", "Key works. Enter your credit balance in Settings to track it.")
    return "ok"


def _health_claude_subscription() -> str:
    from .services import limit_active
    llm.ping()                                       # raises NotConfigured when not signed in (no limit used)
    row = db.select("services", {"name": "anthropic"}, single=True) or {}
    if (row.get("details") or {}).get("auth_rejected"):
        raise NotConfigured("anthropic", "Claude rejected the saved sign-in")
    details = dict(row.get("details") or {})
    details["backend"] = "subscription"
    try:
        from . import usage
        details.update(usage.refresh())
    except Exception as e:
        log.warning(f"claude usage refresh: {e}")
    if limit_active(row):
        db.update("services", {"name": "anthropic"}, {"details": details, "checked_at": now().isoformat()})
        return "warning"
    details.pop("limited", None)
    details.pop("resume_at", None)
    set_status("anthropic", "ok", "Connected (Claude subscription)", details=details)
    return "ok"


def _health_voice() -> str:
    info = voice.health()
    set_status("voice", "ok", None, balance=info["voices"], unit="voices")
    return "ok"


def _health_runpod() -> str:
    key = secrets.get("runpod_api_key")
    if not key:
        set_status("runpod", "unconfigured", "Add your RunPod API key in Settings")
        return "unconfigured"
    r = httpx.post("https://api.runpod.io/graphql", headers={"Authorization": f"Bearer {key}"}, timeout=30,
                   json={"query": "query { myself { clientBalance currentSpendPerHr } }"})
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    me = (body.get("data") or {}).get("myself")
    if r.status_code in (401, 403) or (body.get("errors") and not me):
        set_status("runpod", "unconfigured", "RunPod rejected the API key — check it in Settings")
        return "unconfigured"
    if me is None:
        raise RuntimeError(f"RunPod balance unavailable (HTTP {r.status_code})")
    bal = float(me.get("clientBalance") or 0)
    spend.observe_runpod_balance(bal)
    st = "ok" if bal > 2 else ("warning" if bal > 0.3 else "out_of_credits")
    set_status("runpod", st, None if st == "ok" else f"${bal:.2f} left (~{int(bal / 0.1)} videos). Add funds at runpod.io",
               balance=round(bal, 2), unit="usd")
    return st


def _health_tiktok() -> str:
    if not (secrets.get("tiktok_client_key") and secrets.get("tiktok_client_secret")):
        set_status("tiktok", "unconfigured", "Add the TikTok app client key/secret in Settings, then connect accounts")
        return "unconfigured"
    accs = db.select("tiktok_accounts", columns="id,username,status")
    bad = [a for a in accs if a["status"] != "connected"]
    if not accs:
        set_status("tiktok", "warning", "App keys saved — connect your first TikTok account in Accounts")
        return "warning"
    if bad:
        set_status("tiktok", "warning", f"{len(bad)} account(s) need reconnecting: " +
                   ", ".join("@" + (a.get("username") or "?") for a in bad))
        return "warning"
    set_status("tiktok", "ok", None, balance=len(accs), unit="accounts")
    return "ok"


def _health_storage() -> str:
    gb = _bucket_bytes("videos") / 1e9
    limit = float(settings.get().get("storage_limit_gb", 1.0))
    st = "ok" if gb < limit * 0.8 else ("warning" if gb < limit else "down")
    set_status("storage", st, None if st == "ok" else f"Using {gb:.2f} GB of ~{limit:.0f} GB. Lower retention days in Settings.",
               balance=round(gb, 3), unit="GB", limit=limit)
    return st


def health_check() -> dict:
    out: dict = {}
    try:
        for name, fn in (("anthropic", _health_anthropic), ("voice", _health_voice),
                         ("runpod", _health_runpod), ("tiktok", _health_tiktok), ("storage", _health_storage)):
            _section(name, fn, out)
    finally:
        try:
            _resume_waiting()
        except Exception as e:
            log.warning(f"resume waiting: {e}")
    return out


def _keep_or_report(p: ServiceProblem) -> None:
    from .services import report_problem
    report_problem(p)


def _bucket_bytes(bucket: str, prefix: str = "") -> int:
    total = 0
    for o in db.list_objects(bucket, prefix):
        if o.get("id") is None:                     # folder
            total += _bucket_bytes(bucket, f"{prefix}{o['name']}/")
        else:
            total += int((o.get("metadata") or {}).get("size") or 0)
    return total


def _resume_waiting() -> None:
    """Re-queue jobs parked on a service that is healthy again; clear channel block reasons."""
    from .services import limit_active
    rows = db.select("services")
    st = {r["name"]: r["status"] for r in rows}
    limited = {r["name"] for r in rows if limit_active(r)}
    waiting = db.select("jobs", {"status": "waiting"})
    for j in waiting:
        svc = j.get("waiting_on")
        if svc == "budget":
            from .spend import over_budget
            if over_budget():
                continue
        else:
            cur = st.get(svc)
            if j.get("parked_status") == "limited":
                if svc in limited and not (svc == "anthropic" and llm.fallback_room()):
                    continue
                cur = "ok"                           # the limit has reset
            # out-of-credits needs a real recovery ('ok'); a 'warning' would just fail again
            healthy = cur == "ok" or (cur == "warning" and j.get("parked_status") != "out_of_credits")
            if not healthy:
                continue
        db.update("jobs", {"id": j["id"]}, {"status": "queued", "waiting_on": None, "run_after": now().isoformat()})
        if j.get("video_id"):
            restore = j.get("prev_video_status") or "queued"
            db.update("videos", {"id": j["video_id"], "status": "blocked"}, {"status": restore, "error": None,
                                                                              "stage_detail": "Resuming"})
    for ch in db.select("channels", {"blocked_reason": ("not.is", "null")}):
        if ch["blocked_reason"].startswith("Stopped making new videos"):
            continue                                 # circuit breaker: only the owner's Start clears it
        still = db.select("jobs", {"channel_id": ch["id"], "status": "waiting"}, limit=1)
        if not still:
            db.update("channels", {"id": ch["id"]}, {"blocked_reason": None})
            event(f"{ch['name']} is running again", "success", "services", channel_id=ch["id"])


def refresh_tokens() -> dict:
    n = 0
    soon = (now() + timedelta(hours=2)).isoformat()
    for a in db.select("tiktok_accounts", {"status": "connected", "access_expires_at": ("lt", soon)}):
        try:
            tiktok.refresh(a)
            n += 1
        except Exception as e:
            log.warning(f"refresh failed for {a.get('username')}: {e}")
    return {"refreshed": n}


# ------------------------------------------------------------------ backups & cleanup
BACKUP_TABLES = ["channels", "ideas", "videos", "video_stats", "account_stats", "tiktok_accounts", "settings",
                 "secrets", "reports", "spend", "events", "services"]


_PK = {"settings": "key", "secrets": "key", "services": "name"}


def backup_db() -> dict:
    """Streams every table (ordered by primary key, keyset-paginated) into a gzip JSON file in the `backups` bucket."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(json.dumps({"created_at": now().isoformat()})[:-1].encode() + b', "tables": {')
        for ti, t in enumerate(BACKUP_TABLES):
            pk = _PK.get(t, "id")
            gz.write((("," if ti else "") + json.dumps(t) + ": [").encode())
            last, first = None, True
            while True:
                params = {"select": "*", "limit": "1000", "order": f"{pk}.asc"}
                if last is not None:
                    params[pk] = f"gt.{last}"
                if t == "events":
                    params["created_at"] = f"gte.{(now() - timedelta(days=7)).isoformat()}"
                r = db.client().get(f"/rest/v1/{t}", params=params)
                r.raise_for_status()
                batch = r.json()
                for row in batch:
                    gz.write((("" if first else ",") + json.dumps(row, default=str)).encode())
                    first = False
                if len(batch) < 1000:
                    break
                last = batch[-1][pk]
            gz.write(b"]")
        gz.write(b"}}")
    data = buf.getvalue()
    path = f"db/{date.today().isoformat()}.json.gz"
    db.upload("backups", path, data, "application/gzip")
    objs = sorted(o["name"] for o in db.list_objects("backups", "db/") if o.get("id"))
    if len(objs) > 30:                                   # keep 30 days
        db.remove("backups", [f"db/{n}" for n in objs[:-30]])
    event(f"Backup saved ({len(data) / 1e6:.1f} MB)", "success", "backup")
    return {"path": path, "bytes": len(data)}


def _sweep_local(days: int = 3) -> int:
    """Remove leftover local work dirs (failed videos, killed renders)."""
    import shutil
    import time as _t
    cutoff, n = _t.time() - days * 86400, 0
    for d in list((config.WORK / "videos").glob("*")) + list(config.WORK.glob("render_*")):
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        except OSError:
            pass
    return n


def _storage_paths(base: str, *, everything: bool) -> list[str]:
    paths = [f"{base}/voice.mp3", f"{base}/words.json"] + [f"{base}/scenes/{o['name']}"
                                                         for o in db.list_objects("videos", f"{base}/scenes/")]
    if everything:
        paths += [f"{base}/final.mp4", f"{base}/preview.mp4"]
    return paths


def _sweep_library(keep_days_after_post: int = 2) -> int:
    """Full-quality files on the VPS: drop them once the video is posted (plus a little slack), rejected or gone."""
    from . import pipeline
    lib = pipeline.library_path("x").parent
    files = list(lib.glob("*.mp4")) if lib.exists() else []
    n, cutoff = 0, now() - timedelta(days=keep_days_after_post)
    for f in files:
        row = db.select("videos", {"id": f.stem}, single=True, columns="id,status,posted_at")
        posted = datetime.fromisoformat(row["posted_at"]) if row and row.get("posted_at") else None
        if not row or row["status"] == "rejected" or (posted and posted < cutoff):
            f.unlink(missing_ok=True)
            n += 1
    for f in lib.glob("*.part") if lib.exists() else []:
        f.unlink(missing_ok=True)
    return n


def cleanup_storage() -> dict:
    """Keep Supabase inside the free plan: after posting, the re-render inputs go after 1 day and the preview
    after `video_retention_days` (default 7). Thumbnails and all rows/stats stay."""
    days = int(settings.get().get("video_retention_days") or 7)
    cutoff = (now() - timedelta(days=days)).isoformat()
    n = 0
    for v in db.select("videos", {"posted_at": ("lt", (now() - timedelta(days=1)).isoformat()),
                                  "audio_path": ("not.is", "null")}):
        ch = db.select("channels", {"id": v["channel_id"]}, single=True, columns="slug")
        db.remove("videos", _storage_paths(f"{ch['slug']}/{v['id']}", everything=False))
        db.update("videos", {"id": v["id"]}, {"audio_path": None})
    old = db.select("videos", {"posted_at": ("lt", cutoff), "video_path": ("not.is", "null")})
    rejected = db.select("videos", {"status": "rejected", "updated_at": ("lt", (now() - timedelta(days=3)).isoformat()),
                                    "video_path": ("not.is", "null")})
    for v in old + rejected:
        ch = db.select("channels", {"id": v["channel_id"]}, single=True, columns="slug")
        db.remove("videos", _storage_paths(f"{ch['slug']}/{v['id']}", everything=True))
        db.update("videos", {"id": v["id"]}, {"video_path": None, "audio_path": None})
        n += 1
    # old events / finished jobs
    db.delete("events", {"created_at": ("lt", (now() - timedelta(days=60)).isoformat())})
    db.delete("jobs", {"status": ("in", ["done", "cancelled"]), "finished_at": ("lt", (now() - timedelta(days=14)).isoformat())})
    db.delete("oauth_states", {"created_at": ("lt", (now() - timedelta(hours=1)).isoformat())})
    return {"videos_cleaned": n, "local_dirs_removed": _sweep_local(), "library_files_removed": _sweep_library()}
