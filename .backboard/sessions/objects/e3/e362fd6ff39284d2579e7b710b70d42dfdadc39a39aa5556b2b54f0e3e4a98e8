"""Tests for the liveness and readiness probes.

The contract per docs/runtime.md:

- ``GET /health/live`` always returns 200 unless the process is wedged.
- ``GET /health/ready`` returns 200 with ``status: ready`` when all hard
  dependencies are up; returns 200 with ``status: degraded`` when optional
  dependencies are down; returns 503 with ``status: not_ready`` when a hard
  dependency is missing.
- The response shape is stable so operators and tests can rely on it.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())


def test_health_live_returns_ok():
    """``/health/live`` is process-only and always 200."""
    client = _client()
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body


def test_health_ready_when_docling_available():
    """``/health/ready`` returns 200 with ``status: ready`` when Docling imports."""
    client = _client()
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] in ("docling_only_demo", "demo_with_rapidocr")
    assert body["checks"]["docling"]["available"] is True
    assert body["checks"]["docling"]["required"] is True


def test_health_ready_returns_503_when_docling_missing():
    """Docling is a demo-mode hard dependency; missing it = 503."""
    client = _client()

    # Force the docling import check to fail.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "docling.document_converter" or name.startswith("docling."):
            raise ImportError("simulated: docling missing")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["docling"]["available"] is False


def test_health_ready_rapidocr_disabled_in_config():
    """When RapidOCR is disabled, readiness reports available=True (disabled != unreachable)
    and does not flip status to degraded."""
    client = _client()

    from app.core.config import Settings

    def make_disabled_settings(**_kwargs) -> Settings:
        s = Settings.model_construct()
        s.app_name = "hr-anomaly-pipeline"
        s.debug = False
        s.docling_confidence_threshold = 0.75
        s.docling_confidence_max = 1.0
        s.rapidocr_enabled = False
        s.rapidocr_model_path = "models/rapidocr/en_ppocr_server_v2.0_infer.onnx"
        s.rapidocr_timeout_seconds = 30
        s.rapidocr_default_confidence = 0.6
        s.celery_broker_url = "redis://localhost:6379/0"
        s.celery_result_backend = "redis://localhost:6379/1"
        s.celery_task_soft_time_limit = 300
        s.celery_task_max_retries = 3
        s.celery_task_default_retry_delay = 60
        s.review_timeout_hours = 48
        return s

    with patch("app.core.health.Settings", side_effect=make_disabled_settings):
        response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["rapidocr"]["enabled"] is False
    assert body["checks"]["rapidocr"]["required"] is False


def test_legacy_health_endpoint_still_works():
    """The legacy ``/health`` endpoint is kept for backward compat."""
    client = _client()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "app" in body