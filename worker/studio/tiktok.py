"""Official TikTok APIs (Login Kit tokens, Content Posting API, Display API). See docs/tiktok-api-notes.md."""
from __future__ import annotations

import math
import threading
from datetime import datetime, timedelta, timezone

import httpx

from . import config, crypto, db, secrets
from .log import event
from .services import NotConfigured, ServiceDown, set_status

API = "https://open.tiktokapis.com"
VIDEO_FIELDS = "id,create_time,cover_image_url,share_url,title,video_description,duration,like_count,comment_count,share_count,view_count"
USER_FIELDS = "open_id,avatar_url,display_name,username,is_verified,follower_count,following_count,likes_count,video_count"


class TikTokError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 0):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.status = code, message, status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _app() -> tuple[str, str]:
    ck, cs = secrets.get("tiktok_client_key"), secrets.get("tiktok_client_secret")
    if not ck or not cs:
        raise NotConfigured("tiktok", "TikTok app keys are not saved in Settings")
    return ck, cs


def _check(r: httpx.Response) -> dict:
    try:
        d = r.json()
    except Exception:
        raise TikTokError("bad_response", r.text[:200], r.status_code)
    err = d.get("error") or {}
    code = err.get("code") if isinstance(err, dict) else None
    if r.status_code >= 400 or (code and code != "ok"):
        if r.status_code >= 500:
            raise ServiceDown("tiktok", f"TikTok API {r.status_code} (will retry)")
        raise TikTokError(code or d.get("error", "error"), (err.get("message") if isinstance(err, dict) else "")
                          or d.get("error_description", ""), r.status_code)
    return d


# ------------------------------------------------------------------ tokens
_refresh_lock = threading.Lock()
_DEAD = ("invalid_grant", "invalid_token", "invalid_request", "access_denied")


def refresh(account: dict) -> dict:
    """Refresh tokens. Refresh tokens ROTATE, so this is serialized in-process and compare-and-swap in the DB."""
    with _refresh_lock:
        ck, cs = _app()
        full = db.select("tiktok_accounts", {"id": account["id"]}, single=True)
        old_enc = full["refresh_token_enc"]
        exp = full.get("access_expires_at")
        if exp and datetime.fromisoformat(exp) > _now() + timedelta(minutes=30) and account.get("_force") is not True:
            return {"skipped": "fresh"}          # another caller already refreshed
        try:
            r = httpx.post(f"{API}/v2/oauth/token/", data={"client_key": ck, "client_secret": cs,
                                                          "grant_type": "refresh_token",
                                                          "refresh_token": crypto.decrypt(old_enc)},
                           headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        except httpx.TransportError as e:
            raise ServiceDown("tiktok", f"Cannot reach TikTok: {e}") from e
        if r.status_code >= 500 or r.status_code == 429:
            raise ServiceDown("tiktok", f"TikTok token endpoint {r.status_code} (will retry)")
        try:
            d = r.json()
        except Exception:
            raise ServiceDown("tiktok", f"TikTok token endpoint returned non-JSON ({r.status_code})")
        if "access_token" not in d:
            now_row = db.select("tiktok_accounts", {"id": account["id"]}, single=True, columns="refresh_token_enc")
            if now_row and now_row["refresh_token_enc"] != old_enc:
                return {"skipped": "rotated elsewhere"}
            err = d.get("error") or "refresh_failed"
            if isinstance(err, dict):
                err = err.get("code", "refresh_failed")
            if err in _DEAD:
                db.update("tiktok_accounts", {"id": account["id"]},
                          {"status": "expired", "status_message": d.get("error_description") or str(d)[:200]})
                event(f"TikTok account @{full.get('username')} needs reconnecting: {d.get('error_description')}",
                      "error", "tiktok")
            raise TikTokError(str(err), d.get("error_description", ""))
        vals = {"access_token_enc": crypto.encrypt(d["access_token"]),
                "refresh_token_enc": crypto.encrypt(d["refresh_token"]),
                "access_expires_at": (_now() + timedelta(seconds=int(d["expires_in"]))).isoformat(),
                "refresh_expires_at": (_now() + timedelta(seconds=int(d.get("refresh_expires_in", 0)))).isoformat(),
                "scopes": [x for x in d.get("scope", "").split(",") if x], "status": "connected", "status_message": None}
        db.update("tiktok_accounts", {"id": account["id"], "refresh_token_enc": old_enc}, vals)
        return d


def token(account_id: str) -> str:
    acc = db.select("tiktok_accounts", {"id": account_id}, single=True)
    if not acc:
        raise NotConfigured("tiktok", "TikTok account not found")
    if acc["status"] in ("revoked",):
        raise NotConfigured("tiktok", f"TikTok account @{acc.get('username')} was disconnected")
    exp = acc.get("access_expires_at")
    if not exp or datetime.fromisoformat(exp) < _now() + timedelta(minutes=10):
        refresh(acc)
        acc = db.select("tiktok_accounts", {"id": account_id}, single=True)
    return crypto.decrypt(acc["access_token_enc"])


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}


# ------------------------------------------------------------------ info
def user_info(account_id: str) -> dict:
    r = httpx.get(f"{API}/v2/user/info/", params={"fields": USER_FIELDS}, headers=_auth(token(account_id)), timeout=30)
    return _check(r)["data"]["user"]


def creator_info(account_id: str) -> dict:
    r = httpx.post(f"{API}/v2/post/publish/creator_info/query/", headers=_auth(token(account_id)), timeout=30)
    return _check(r)["data"]


def query_videos(account_id: str, ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 20):
        r = httpx.post(f"{API}/v2/video/query/", params={"fields": VIDEO_FIELDS},
                       json={"filters": {"video_ids": ids[i:i + 20]}}, headers=_auth(token(account_id)), timeout=30)
        out += _check(r)["data"].get("videos", [])
    return out


def list_videos(account_id: str, max_pages: int = 5) -> list[dict]:
    out, cursor = [], None
    for _ in range(max_pages):
        body = {"max_count": 20}
        if cursor:
            body["cursor"] = cursor
        r = httpx.post(f"{API}/v2/video/list/", params={"fields": VIDEO_FIELDS}, json=body,
                       headers=_auth(token(account_id)), timeout=30)
        d = _check(r)["data"]
        out += d.get("videos", [])
        if not d.get("has_more"):
            break
        cursor = d.get("cursor")
    return out


# ------------------------------------------------------------------ posting
def _chunks(size: int) -> tuple[int, int]:
    """TikTok: chunks 5–64 MB (last up to 128 MB); files ≤ 64 MB may go as a single chunk."""
    MB = 1024 * 1024
    if size <= 64 * MB:
        return size, 1
    chunk = 10 * MB
    return chunk, size // chunk


def _put_file(upload_url: str, data: bytes, chunk: int, count: int) -> None:
    size = len(data)
    with httpx.Client(timeout=300) as c:
        for i in range(count):
            a = i * chunk
            b = size - 1 if i == count - 1 else a + chunk - 1
            part = data[a:b + 1]
            for attempt in range(3):
                r = c.put(upload_url, content=part, headers={"Content-Type": "video/mp4",
                                                             "Content-Length": str(len(part)),
                                                             "Content-Range": f"bytes {a}-{b}/{size}"})
                if r.status_code in (200, 201, 206):
                    break
                if r.status_code < 500 or attempt == 2:
                    raise TikTokError("upload_failed", f"chunk {i} -> {r.status_code} {r.text[:200]}", r.status_code)


def post_video(account_id: str, data: bytes, *, mode: str, title: str, aigc: bool = True,
               cover_ms: int = 0) -> str:
    """mode: 'draft' (inbox), 'private' (SELF_ONLY), 'public'. Returns publish_id."""
    if config.DRY_RUN:
        return "dry-run"
    tok = token(account_id)
    chunk, count = _chunks(len(data))
    source = {"source": "FILE_UPLOAD", "video_size": len(data), "chunk_size": chunk, "total_chunk_count": count}
    if mode == "draft":
        r = httpx.post(f"{API}/v2/post/publish/inbox/video/init/", json={"source_info": source}, headers=_auth(tok),
                       timeout=60)
    else:
        info = creator_info(account_id)
        opts = info.get("privacy_level_options") or []
        want = "PUBLIC_TO_EVERYONE" if mode == "public" else "SELF_ONLY"
        if want not in opts:
            raise TikTokError("privacy_level_option_mismatch", f"{want} not allowed; account offers {opts}")
        post_info = {"title": title[:2200], "privacy_level": want, "disable_duet": False, "disable_comment": False,
                     "disable_stitch": False, "video_cover_timestamp_ms": cover_ms, "brand_content_toggle": False,
                     "brand_organic_toggle": False, "is_aigc": aigc}
        r = httpx.post(f"{API}/v2/post/publish/video/init/", json={"post_info": post_info, "source_info": source},
                       headers=_auth(tok), timeout=60)
    d = _check(r)["data"]
    _put_file(d["upload_url"], data, chunk, count)
    set_status("tiktok", "ok", None)
    return d["publish_id"]


def publish_status(account_id: str, publish_id: str) -> dict:
    r = httpx.post(f"{API}/v2/post/publish/status/fetch/", json={"publish_id": publish_id},
                   headers=_auth(token(account_id)), timeout=30)
    return _check(r)["data"]
