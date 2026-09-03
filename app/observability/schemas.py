"""Observability event schema for the extraction pipeline.

STAR-driven design:
  Situation — the base scaffold's StageResult/JobState carry only the
  latest state (doc_id, statut, confiance, flags). There is no durable,
  queryable trail of *what happened at each stage* (Docling attempt,
  RapidOCR fallback, validation outcome, anomaly scoring), so a reviewer
  or engineer cannot answer "why did this document take 4s?" or "how
  often does RapidOCR rescue a low-confidence Docling read?" without
  reading logs by hand.
  Task — define one canonical, stage-agnostic event schema that every
  pipeline stage emits exactly once, so metrics/traces/logs/lineage all
  derive from the same source of truth instead of four divergent ad-hoc
  logging statements.
  Action — introduce `PipelineStageEvent` (below) and a `PipelineRunSummary`
  aggregate; emit one `PipelineStageEvent` per stage via
  `app.observability.tracing.observe_stage`, which simultaneously feeds
  OpenTelemetry spans, Prometheus counters/histograms, structured JSON
  logs, and an OpenLineage-style run event.
  Result — a single instrumentation point gives full observability
  (traces + metrics + logs + lineage) with no per-stage boilerplate, and
  the schema below is what reviewers/Grafana/Loki actually query.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class PipelineStage(StrEnum):
    UPLOAD_PREFLIGHT = "upload_preflight"
    DOCLING_EXTRACTION = "docling_extraction"
    RAPIDOCR_FALLBACK = "rapidocr_fallback"
    FIELD_EXTRACTION = "field_extraction"
    SCHEMA_VALIDATION = "schema_validation"
    ANOMALY_DETECTION = "anomaly_detection"
    REPORT_BUILD = "report_build"


class StageOutcome(StrEnum):
    SUCCESS = "success"
    DEGRADED = "degraded"          # e.g. Docling below confidence, kept for review
    FALLBACK_USED = "fallback_used"  # RapidOCR rescued a low-confidence read
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStageEvent(BaseModel):
    """One immutable record of a single stage execution for one document.

    This is the atomic unit of observability. Every exporter (metrics,
    traces, logs, lineage) is a pure projection of this event -- add a
    field here once, and it becomes queryable everywhere.
    """

    event_id: str = Field(..., description="UUID for this specific event")
    doc_id: str = Field(..., description="Correlates all events for one document")
    run_id: str = Field(..., description="Correlates all events for one pipeline execution (== doc_id.revision)")
    revision: int = Field(default=1)
    stage: PipelineStage
    outcome: StageOutcome
    started_at: datetime
    finished_at: datetime
    duration_ms: float = Field(..., ge=0.0)
    source: Optional[Literal["docling", "rapidocr", "rules", "isolation_forest", "ecod"]] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    anomaly_count: Optional[int] = Field(default=None, ge=0)
    anomaly_max_severity: Optional[Literal["INFO", "WARNING", "ERROR", "CRITICAL"]] = None
    input_bytes: Optional[int] = Field(default=None, ge=0)
    cohort_key: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def now_utc(cls) -> datetime:
        return datetime.now(timezone.utc)


class PipelineRunSummary(BaseModel):
    """Aggregate view of every stage event for one document run.

    Built by folding all `PipelineStageEvent`s for a `run_id`; this is
    what a debugging dashboard or the /observability/{doc_id} endpoint
    returns -- the full timeline in one payload, still without exposing
    the underlying HR data (mirrors the report.py privacy stance).
    """

    doc_id: str
    run_id: str
    revision: int
    total_duration_ms: float
    stages: list[PipelineStageEvent]
    final_status: Literal["ACCEPTED", "REVIEW_REQUIRED", "REJECTED", "FAILED"]
    ocr_fallback_used: bool
    bottleneck_stage: Optional[PipelineStage] = None
