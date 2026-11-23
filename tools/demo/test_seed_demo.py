"""Integration test for the demo copy's data. Skips unless the local demo Supabase is running (bash tools/demo/up.sh)."""
import collections
import sys
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    httpx.get("http://127.0.0.1:54321/rest/v1/", timeout=2)
    UP = True
except Exception:
    UP = False

pytestmark = pytest.mark.skipif(not UP, reason="local demo Supabase not running")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    import seed_demo
    renders = HERE / ".renders"
    first = seed_demo.run(renders)
    second = seed_demo.run(renders)
    return seed_demo, first, second


def test_seed_has_full_lifecycle(seeded):
    seed_demo, first, second = seeded
    db = seed_demo.db
    vids = db.select("videos", {"experiment->>demo": "true"})
    statuses = collections.Counter(v["status"] for v in vids)
    assert {"ready", "scheduled", "posted", "failed", "voice", "rejected"} <= set(statuses)
    assert statuses["posted"] >= 5
    pending = [v for v in vids if v["status"] == "ready" and v["approval"] == "pending"]
    assert len(pending) == 1
    for v in (v for v in vids if v["status"] == "posted"):
        assert len(db.select("video_stats", {"video_id": v["id"]}, columns="id")) >= 20
    assert any(len(v["title"]) >= 90 for v in vids)
    assert sum(float(v["cost_usd"]) for v in vids) > 0
    assert len(db.select("reports", {"data->>demo": "true"})) == 1
    ch = db.select("channels", {"slug": "overthought"}, single=True)
    assert ch["strategy"] and ch["status"] == "active"
    assert len(db.select("events", {"data->>demo": "true"}, columns="id")) >= 8
    assert len(db.select("jobs", {"payload->>demo": "true"}, columns="id")) >= 3
    assert all(s["status"] == "ok" for s in db.select("services"))
    assert first == second


def test_red_bar_toggle(seeded):
    seed_demo = seeded[0]
    seed_demo.set_red_bar(True)
    assert seed_demo.db.select("services", {"name": "elevenlabs"}, single=True)["status"] == "out_of_credits"
    seed_demo.set_red_bar(False)
    assert seed_demo.db.select("services", {"name": "elevenlabs"}, single=True)["status"] == "ok"
