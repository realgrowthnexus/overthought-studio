"""RunPod client: async /run + status polling, every network error parks the job (ServiceDown)."""
import io

import httpx
import pytest
from PIL import Image

from studio import images, spend
from studio.services import ServiceDown

from fakes import install

REAL_GENERATE = images.generate
PNG = io.BytesIO()
Image.new("RGB", (8, 8)).save(PNG, "PNG")


@pytest.fixture
def rp(monkeypatch, tmp_path):
    install(monkeypatch, tmp_path / "work")
    monkeypatch.setattr(images, "generate", REAL_GENERATE)
    monkeypatch.setattr(images.time, "sleep", lambda s: None)
    monkeypatch.setattr(spend, "record", lambda *a, **k: None)
    monkeypatch.setattr(images, "set_status", lambda *a, **k: None)
    seen = []

    def use(handler):
        real = httpx.Client

        def client(*a, **k):
            k["transport"] = httpx.MockTransport(lambda req: (seen.append(req), handler(req))[1])
            return real(*a, **k)
        monkeypatch.setattr(images.httpx, "Client", client)
        return seen
    return use


def test_completed_job_returns_image(rp):
    def h(req):
        if req.url.path.endswith("/run"):
            return httpx.Response(200, json={"id": "j1", "status": "IN_QUEUE"})
        if "/status/" in req.url.path:
            return httpx.Response(200, json={"id": "j1", "status": "COMPLETED", "output": {"image_url": "https://img.example/x.png"}})
        return httpx.Response(200, content=PNG.getvalue())
    seen = rp(h)
    img, cost = images.generate("a stick figure")
    assert img.size == (8, 8) and cost > 0
    assert [r.url.path.rsplit("/", 1)[-1] for r in seen][:1] == ["run"]


def test_poll_network_error_is_service_down(rp):
    def h(req):
        if req.url.path.endswith("/run"):
            return httpx.Response(200, json={"id": "j1", "status": "IN_QUEUE"})
        raise httpx.ConnectError("boom")
    seen = rp(h)
    with pytest.raises(ServiceDown):
        images.generate("a stick figure")
    assert seen[0].url.path.endswith("/run") and len(seen) >= 2        # failed while polling, not on submit


def test_image_download_error_is_service_down(rp):
    def h(req):
        if req.url.path.endswith("/run"):
            return httpx.Response(200, json={"id": "j1", "status": "COMPLETED", "output": {"image_url": "https://img.example/x.png"}})
        return httpx.Response(503, text="bad gateway")
    seen = rp(h)
    with pytest.raises(ServiceDown):
        images.generate("a stick figure")
    assert seen[0].url.path.endswith("/run") and len(seen) == 2


def test_poll_blip_is_retried_with_the_same_job(rp):
    state = {"n": 0}

    def h(req):
        if req.url.path.endswith("/run"):
            return httpx.Response(200, json={"id": "j1", "status": "IN_QUEUE"})
        if "/status/" in req.url.path:
            state["n"] += 1
            if state["n"] == 1:
                raise httpx.ReadTimeout("blip")
            return httpx.Response(200, json={"id": "j1", "status": "COMPLETED", "output": {"image_url": "https://img.example/x.png"}})
        return httpx.Response(200, content=PNG.getvalue())
    seen = rp(h)
    images.generate("a stick figure")
    assert sum(r.url.path.endswith("/run") for r in seen) == 1
