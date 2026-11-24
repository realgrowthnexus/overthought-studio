"""RunPod hard monthly cap: real balance drops count, top-ups don't, and images stop before the cap."""
import pytest

from studio import images, settings, spend
from fakes import install

REAL_GENERATE = images.generate


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = install(monkeypatch, tmp_path / "work")
    monkeypatch.setattr(images, "generate", REAL_GENERATE)
    settings._cache.clear()
    return w


def _cap(v):
    g = settings.get(ttl=0); g["runpod_monthly_cap_usd"] = v; settings.put("global", g)


def test_balance_meter_counts_drops_not_topups(world):
    spend.observe_runpod_balance(50.0)
    spend.observe_runpod_balance(47.5)        # spent 2.5
    spend.observe_runpod_balance(97.5)        # top-up of 50: not spending
    spend.observe_runpod_balance(96.0)        # spent 1.5
    assert spend.runpod_month() == pytest.approx(4.0)


def test_cap_blocks_images_and_production(world, monkeypatch):
    _cap(10)
    calls = []
    monkeypatch.setattr(images, "_generate", lambda *a, **k: calls.append(1) or (None, 0.0))
    spend.observe_runpod_balance(100.0)
    images.generate("a door")                 # well under the cap
    assert calls == [1] and spend.over_budget() is None
    spend.observe_runpod_balance(91.0)        # real spend 9 → within the $1 safety margin of $10
    with pytest.raises(spend.BudgetReached):
        images.generate("a door")
    assert calls == [1]                       # RunPod was never called
    assert "RunPod monthly cap" in (spend.over_budget() or "")
    _cap(0)                                   # 0 = no cap
    assert spend.runpod_cap_message() is None


def test_ledger_counts_when_balance_not_seen_yet(world):
    _cap(5)
    for _ in range(400):
        spend.record("runpod", 0.012)          # $4.80 by our estimate
    assert spend.runpod_cap_message() is not None
