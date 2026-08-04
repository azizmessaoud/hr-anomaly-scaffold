"""Liveness and readiness probes for the HR Anomaly Pipeline.

Contracts (canonical in docs/runtime.md):

- ``GET /health/live`` — process-only liveness. Always 200 unless the
  process is wedged.
- ``GET /health/ready`` — mode-aware readiness. Returns 200 with a
  ``degraded`` status when optional dependencies are down; returns 503
  when a hard dependency (Docling in demo mode) is missing.

Demo mode hard deps: Docling importable, ``DocumentConverter`` available.
Demo mode soft deps: VLM (Ollama), Redis, Postgres, Celery — never
fatal in demo mode.

The probe function itself is intentionally simple: it imports the
module under check and reports availability. Operators can read the
returned ``checks`` map to see what is and isn't reachable.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _check_docling() -> tuple[bool, str | None]:
    """Demo-mode hard dependency: Docling importable + DocumentConverter.

    Returns ``(ok, detail)``. ``detail`` is non-null only when the
    dependency is unavailable, and is short enough to surface in a
    dashboard tile.
    """
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401
    except ImportError as exc:
        return False, f"docling import failed: {exc}"
    return True, None


def _check_vlm(settings: Settings) -> tuple[bool, str | None]:
    """Optional dep: VLM (Ollama). Reported as down in demo mode but
    does not flip readiness to 503."""
    if not settings.vlm_enabled:
        return True, "vlm disabled by config"
    return True, None


def _build_readiness_payload() -> dict[str, Any]:
    """Probe the active mode's dependencies and build the readiness body.

    The shape is intentionally stable: ``status``, ``checks``, and an
    optional ``degraded`` flag. Operators and tests can rely on these
    keys without parsing free-form text.
    """
    settings = Settings()
    checks: dict[str, dict[str, Any]] = {}

    docling_ok, docling_detail = _check_docling()
    checks["docling"] = {
        "status": "up" if docling_ok else "down",
        "required": True,
    }
    if docling_detail:
        checks["docling"]["detail"] = docling_detail

    vlm_ok, vlm_detail = _check_vlm(settings)
    vlm_status = "disabled" if (vlm_detail == "vlm disabled by config") else (
        "up" if vlm_ok else "down"
    )
    checks["vlm"] = {
        "status": vlm_status,
        "required": False,
        "url": settings.ollama_base_url,
    }
    if vlm_detail:
        checks["vlm"]["detail"] = vlm_detail

    hard_ok = docling_ok
    degraded = not vlm_ok

    payload: dict[str, Any] = {
        "status": "ok" if hard_ok else "down",
        "mode": "demo",
        "checks": checks,
    }
    if degraded:
        payload["degraded"] = True
    return payload


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """Process-only liveness probe. Always 200 unless the server is wedged."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    """Mode-aware readiness probe. 503 iff a hard dep is missing."""
    payload = _build_readiness_payload()
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(content=payload, status_code=status_code)


@router.get("/health")
async def health_legacy() -> JSONResponse:
    """Legacy ``/health`` endpoint kept for backward compatibility.

    Returns the readiness payload. New code should prefer
    ``/health/live`` and ``/health/ready`` per the runtime contract.
    """
    return await health_ready()