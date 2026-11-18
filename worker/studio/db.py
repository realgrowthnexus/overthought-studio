"""Thin Supabase client (PostgREST + Storage) over httpx, using the service-role key.

Only the `apikey` header is sent: it works with both new `sb_secret_` keys and legacy JWT keys.
"""
from __future__ import annotations

import json
import time
from typing import Any, Iterable

import httpx

from . import config

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        headers = {"apikey": config.SUPABASE_KEY or "proxy-injected"}
        if config.SUPABASE_KEY.startswith("eyJ"):            # legacy JWT service key also needs Bearer
            headers["Authorization"] = f"Bearer {config.SUPABASE_KEY}"
        _client = httpx.Client(base_url=config.SUPABASE_URL, headers=headers, timeout=60)
    return _client


class DBError(RuntimeError):
    pass


def _req(method: str, path: str, *, retries: int = 4, **kw) -> httpx.Response:
    last = ""
    for i in range(retries):
        try:
            r = client().request(method, path, **kw)
        except httpx.TransportError as e:
            last = f"transport: {e}"
        else:
            if r.status_code < 400:
                return r
            if r.status_code >= 500 or r.status_code == 429:
                last = f"{r.status_code} {r.text[:300]}"
            else:
                raise DBError(f"{method} {path} -> {r.status_code} {r.text[:500]}")
        time.sleep(1.5 * (i + 1))
    raise DBError(f"{method} {path} failed after {retries} tries: {last}")


def _filters(where: dict[str, Any] | None) -> dict[str, str]:
    """{'id': 'x'} -> eq; {'status': ('in', [...])}; {'score': ('gte', 3)}; raw strings like 'is.null' allowed."""
    params: dict[str, str] = {}
    for k, v in (where or {}).items():
        if isinstance(v, tuple):
            op, val = v
            if op == "in":
                val = "(" + ",".join(json.dumps(x) if not isinstance(x, str) else f'"{x}"' for x in val) + ")"
            params[k] = f"{op}.{val}"
        elif v is None:
            params[k] = "is.null"
        elif isinstance(v, bool):
            params[k] = f"is.{str(v).lower()}"
        else:
            params[k] = f"eq.{v}"
    return params


def select(table: str, where: dict | None = None, *, columns: str = "*", order: str | None = None,
           limit: int | None = None, single: bool = False) -> Any:
    params = _filters(where)
    params["select"] = columns
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)
    r = _req("GET", f"/rest/v1/{table}", params=params)
    rows = r.json()
    if single:
        return rows[0] if rows else None
    return rows


def insert(table: str, rows: dict | list[dict], *, upsert: bool = False, on_conflict: str | None = None,
           ignore_duplicates: bool = False) -> list[dict]:
    prefer = ["return=representation"]
    if upsert:
        prefer.append("resolution=ignore-duplicates" if ignore_duplicates else "resolution=merge-duplicates")
    params = {"on_conflict": on_conflict} if on_conflict else None
    r = _req("POST", f"/rest/v1/{table}", json=rows, params=params, headers={"Prefer": ",".join(prefer)})
    return r.json() if r.content else []


def update(table: str, where: dict, values: dict) -> list[dict]:
    r = _req("PATCH", f"/rest/v1/{table}", params=_filters(where), json=values,
             headers={"Prefer": "return=representation"})
    return r.json() if r.content else []


def delete(table: str, where: dict) -> None:
    _req("DELETE", f"/rest/v1/{table}", params=_filters(where))


def rpc(fn: str, args: dict | None = None) -> Any:
    r = _req("POST", f"/rest/v1/rpc/{fn}", json=args or {})
    return r.json() if r.content else None


# ---------------- storage ----------------
def upload(bucket: str, path: str, data: bytes, content_type: str) -> str:
    _req("POST", f"/storage/v1/object/{bucket}/{path}", content=data,
         headers={"Content-Type": content_type, "x-upsert": "true"}, timeout=600)
    return path


def download(bucket: str, path: str) -> bytes:
    return _req("GET", f"/storage/v1/object/{bucket}/{path}", timeout=600).content


def remove(bucket: str, paths: Iterable[str]) -> None:
    paths = list(paths)
    if paths:
        _req("DELETE", f"/storage/v1/object/{bucket}", json={"prefixes": paths})


def list_objects(bucket: str, prefix: str = "", limit: int = 1000) -> list[dict]:
    r = _req("POST", f"/storage/v1/object/list/{bucket}", json={"prefix": prefix, "limit": limit,
                                                                 "sortBy": {"column": "name", "order": "asc"}})
    return r.json()


def signed_url(bucket: str, path: str, expires: int = 3600) -> str:
    r = _req("POST", f"/storage/v1/object/sign/{bucket}/{path}", json={"expiresIn": expires})
    return config.SUPABASE_URL + "/storage/v1" + r.json()["signedURL"]
