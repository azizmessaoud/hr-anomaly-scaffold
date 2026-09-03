"""Read-only observability API -- never exposes HR record content.

STAR — mirrors the existing privacy stance of app/pipeline/report.py:
the /observability endpoints return only timing, outcome, and error-code
data (already masked at the schema level), never `HRRecord` fields.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.observability.schemas import PipelineRunSummary
from app.observability.store import get_event_store
from app.ingestion.repository import get_job_repository  # existing in-memory repo

router = APIRouter()


@router.get("/observability/{doc_id}", response_model=PipelineRunSummary)
def get_pipeline_trace(doc_id: str) -> PipelineRunSummary:
    """Full per-stage timeline for one document: durations, outcomes,
    confidence scores, and error codes -- the "why did this take 4s /
    why did RapidOCR kick in" view for engineers and reviewers.
    """
    job = get_job_repository().get(doc_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown doc_id")
    run_id = doc_id  # base scaffold has no separate run_id yet; see README note
    summary = get_event_store().get_run_summary(run_id, final_status=_map_status(job.statut.value))
    if summary is None:
        raise HTTPException(status_code=404, detail="no observability events recorded yet")
    return summary


@router.get("/metrics")
def metrics() -> Response:
    """Prometheus scrape target. Wire this into prometheus.yml as a
    static target on the API container's :8000 port.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _map_status(internal_statut: str) -> str:
    return {"green": "ACCEPTED", "amber": "REVIEW_REQUIRED", "red": "REJECTED"}.get(
        internal_statut, "FAILED"
    )
