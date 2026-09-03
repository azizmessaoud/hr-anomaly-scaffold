"""Minimal OpenLineage-compatible run-event emitter.

STAR — Task: satisfy "observability on the full data extraction pipeline"
at the *lineage* level too -- not just metrics/traces, but "which document
(dataset) went through which stage (job) in which run", using the open
OpenLineage spec (Job / Run / Dataset / Facet) so the events can later be
consumed by Marquez or DataHub without custom glue code.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Literal

import httpx

from app.observability.schemas import PipelineStageEvent

_NAMESPACE = os.getenv("OPENLINEAGE_NAMESPACE", "hr-anomaly-pipeline")
_ENDPOINT = os.getenv("OPENLINEAGE_URL")  # e.g. http://marquez:5000/api/v1/lineage


def emit_run_event(
    event: PipelineStageEvent,
    lineage_state: Literal["START", "COMPLETE", "FAIL", "ABORT"],
) -> None:
    if not _ENDPOINT:
        return  # lineage export is opt-in; no-op keeps demo mode dependency-free
    payload: dict[str, Any] = {
        "eventType": lineage_state,
        "eventTime": event.finished_at.isoformat(),
        "producer": "https://github.com/azizmessaoud/hr-anomaly-scaffold",
        "job": {"namespace": _NAMESPACE, "name": event.stage.value},
        "run": {"runId": str(uuid.uuid5(uuid.NAMESPACE_URL, event.run_id))},
        "inputs": [
            {
                "namespace": _NAMESPACE,
                "name": f"document/{event.doc_id}",
                "facets": {"schema": {"fields": []}},  # HR content intentionally omitted
            }
        ],
        "outputs": [],
    }
    try:
        httpx.post(_ENDPOINT, json=payload, timeout=2.0)
    except httpx.HTTPError:
        pass  # lineage export failures must never break the main pipeline
