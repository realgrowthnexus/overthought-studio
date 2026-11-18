"""Structured logging to stdout and the `events` table (shown in the dashboard)."""
import json
import logging
import sys

from . import db

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("studio")


def event(message: str, level: str = "info", scope: str = "system", *, channel_id=None, video_id=None,
          data=None) -> None:
    getattr(log, {"success": "info", "debug": "debug"}.get(level, level))(f"[{scope}] {message}")
    try:
        db.insert("events", {"level": level, "scope": scope, "message": message[:2000],
                             "channel_id": channel_id, "video_id": video_id,
                             "data": json.loads(json.dumps(data, default=str)) if data else None})
    except Exception as e:  # logging must never break the pipeline
        log.warning(f"could not write event: {e}")
