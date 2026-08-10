from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# /health/live — process-only liveness, no dep checks
# ---------------------------------------------------------------------------


def test_health_live_returns_ok(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body


def test_health_live_does_not_call_out_to_dependencies(client: TestClient):
    """``/health/live`` must not touch the network or probe Docling.
    A live probe that depends on RapidOCR is not a live probe — it's a
    readiness probe in disguise."""
    with patch("app.core.health._docling_importable") as docling_mock:
        with patch("app.core.health._rapidocr_importable") as rapidocr_mock:
            response = client.get("/health/live")
    assert response.status_code == 200
    docling_mock.assert_not_called()
    rapidocr_mock.assert_not_called()


# ---------------------------------------------------------------------------
# /health — back-compat shim, identical to /health/live
# ---------------------------------------------------------------------------


def test_health_backcompat_returns_same_as_live(client: TestClient):
    """Older clients hit ``/health`` directly; keep returning the same
    body so they don't break."""
    live = client.get("/health/live").json()
    legacy = client.get("/health").json()
    assert legacy == live


# ---------------------------------------------------------------------------
# /health/ready — mode-aware readiness probe
# ---------------------------------------------------------------------------


def test_health_ready_returns_200_when_docling_available(client: TestClient):
    """If Docling import works and RapidOCR is disabled, the probe is ready."""
    with patch("app.core.health._docling_importable", return_value=True):
        with patch("app.core.health._rapidocr_importable", return_value=True):
            response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["docling"]["available"] is True
    assert body["checks"]["docling"]["required"] is True


def test_health_ready_returns_503_when_docling_missing(client: TestClient):
    """Missing Docling = hard dep failure = 503."""
    with patch("app.core.health._docling_importable", return_value=False):
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["docling"]["available"] is False


def test_health_ready_returns_200_degraded_when_rapidocr_unreachable(client: TestClient):
    """RapidOCR unreachable is a soft dep — 200 with degraded detail, not 503."""
    with patch("app.core.health._docling_importable", return_value=True):
        with patch("app.core.health._rapidocr_importable", return_value=False):
            response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["rapidocr"]["available"] is False
    assert body["checks"]["rapidocr"]["required"] is False


def test_health_ready_reports_mode_when_rapidocr_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """When ``RAPIDOCR_ENABLED=true`` the probe reports the RapidOCR-aware mode."""
    monkeypatch.setenv("RAPIDOCR_ENABLED", "true")
    monkeypatch.setenv("RAPIDOCR_MODEL_PATH", "models/rapidocr/en_ppocr_server_v2.0_infer.onnx")
    with patch("app.core.health._docling_importable", return_value=True):
        with patch("app.core.health._rapidocr_importable", return_value=True):
            response = client.get("/health/ready")

    body = response.json()
    assert body["mode"] == "demo_with_rapidocr"
    assert body["checks"]["rapidocr"]["enabled"] is True


def test_health_ready_reports_mode_when_rapidocr_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """When ``RAPIDOCR_ENABLED=false`` the probe reports Docling-only mode and
    treats RapidOCR as enabled-and-OK (skipping the import probe)."""
    monkeypatch.setenv("RAPIDOCR_ENABLED", "false")
    monkeypatch.setenv("RAPIDOCR_MODEL_PATH", "models/rapidocr/en_ppocr_server_v2.0_infer.onnx")
    with patch("app.core.health._docling_importable", return_value=True):
        with patch("app.core.health._rapidocr_importable", return_value=True):
            response = client.get("/health/ready")

    body = response.json()
    assert body["mode"] == "docling_only_demo"
    assert body["checks"]["rapidocr"]["enabled"] is False


# ---------------------------------------------------------------------------
# Direct unit tests for the RapidOCR importability probe (no FastAPI)
# ---------------------------------------------------------------------------


def test_rapidocr_importable_returns_false_on_import_error():
    """A missing rapidocr_onnxruntime package must short-circuit to False."""
    from app.core.config import ExtractPipelineConfig
    from app.core.health import _rapidocr_importable

    config = ExtractPipelineConfig(
        docling_confidence_threshold=0.75,
        rapidocr_enabled=True,
        rapidocr_model_path="models/rapidocr/en_ppocr_server_v2.0_infer.onnx",
        rapidocr_timeout_seconds=30,
        rapidocr_default_confidence=0.5,
    )
    with patch.dict("sys.modules", {"rapidocr_onnxruntime": None}):
        import importlib
        import app.core.health
        importlib.reload(app.core.health)
        from app.core.health import _rapidocr_importable
        assert _rapidocr_importable(config) is False


def test_rapidocr_importable_returns_true_when_disabled():
    """When ``RAPIDOCR_ENABLED=false`` the probe must not even attempt the
    import check — disabled is not unreachable."""
    from app.core.config import ExtractPipelineConfig
    from app.core.health import _rapidocr_importable

    config = ExtractPipelineConfig(
        docling_confidence_threshold=0.75,
        rapidocr_enabled=False,
        rapidocr_model_path="models/rapidocr/en_ppocr_server_v2.0_infer.onnx",
        rapidocr_timeout_seconds=30,
        rapidocr_default_confidence=0.5,
    )
    assert _rapidocr_importable(config) is True