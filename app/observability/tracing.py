"""Central instrumentation point: one context manager feeds four sinks.

STAR — Action: instead of instrumenting Docling, RapidOCR, validation, and
anomaly detection separately (four divergent logging styles), every stage
in app/ingestion/tasks.py and app/anomalies/orchestrator.py wraps its body
in `observe_stage(...)`. That single call:
  1. opens an OpenTelemetry span (trace) around the stage,
  2. records duration/outcome into Prometheus metrics,
  3. emits one structured JSON log line,
  4. appends a PipelineStageEvent to the run's event store (SQLite/Postgres),
     which the /observability/{doc_id} endpoint and OpenLineage exporter
     both read from.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from opentelemetry import trace
from prometheus_client import Counter, Histogram

from app.observability.schemas import PipelineStage, PipelineStageEvent, StageOutcome
from app.observability.store import get_event_store

logger = logging.getLogger("hr_pipeline.observability")
tracer = trace.get_tracer("hr-anomaly-pipeline")

STAGE_DURATION_SECONDS = Histogram(
    "hr_pipeline_stage_duration_seconds",
    "Duration of one pipeline stage execution",
    labelnames=("stage", "outcome", "source"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
)
STAGE_EVENTS_TOTAL = Counter(
    "hr_pipeline_stage_events_total",
    "Count of pipeline stage executions by outcome",
    labelnames=("stage", "outcome", "source"),
)
OCR_FALLBACK_TOTAL = Counter(
    "hr_pipeline_ocr_fallback_total",
    "Count of RapidOCR fallback invocations by result",
    labelnames=("result",),  # rescued | still_failed | disabled
)
ANOMALY_FLAGS_TOTAL = Counter(
    "hr_pipeline_anomaly_flags_total",
    "Count of anomaly flags raised by detector and severity",
    labelnames=("detector", "severity"),
)
DOCUMENTS_PROCESSED_TOTAL = Counter(
    "hr_pipeline_documents_processed_total",
    "Terminal documents processed by final report status",
    labelnames=("status",),
)


@contextmanager
def observe_stage(
    *,
    doc_id: str,
    run_id: str,
    revision: int,
    stage: PipelineStage,
    source: Optional[str] = None,
    cohort_key: Optional[str] = None,
) -> Iterator[dict]:
    """Wrap one pipeline stage; yield a mutable dict the caller fills in.

    Usage (inside app/ingestion/tasks.py)::

        with observe_stage(doc_id=doc_id, run_id=run_id, revision=1,
                            stage=PipelineStage.DOCLING_EXTRACTION,
                            source="docling") as ctx:
            result = _extract_embedded_pdf_text(path)
            ctx["outcome"] = StageOutcome.SUCCESS if result else StageOutcome.DEGRADED
            ctx["confidence"] = result.confidence
    """
    started_at = PipelineStageEvent.now_utc()
    start = time.perf_counter()
    ctx: dict = {
        "outcome": StageOutcome.SUCCESS,
        "confidence": None,
        "error_code": None,
        "error_message": None,
        "anomaly_count": None,
        "anomaly_max_severity": None,
        "input_bytes": None,
        "extra": {},
    }
    span_name = f"hr_pipeline.{stage.value}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("doc_id", doc_id)
        span.set_attribute("run_id", run_id)
        span.set_attribute("stage", stage.value)
        if source:
            span.set_attribute("source", source)
        try:
            yield ctx
        except Exception as exc:  # noqa: BLE001 - re-raised after telemetry
            ctx["outcome"] = StageOutcome.FAILED
            ctx["error_code"] = type(exc).__name__
            ctx["error_message"] = str(exc)[:500]
            span.record_exception(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            outcome = ctx["outcome"]
            span.set_attribute("outcome", outcome.value)
            span.set_attribute("duration_ms", duration_ms)

            event = PipelineStageEvent(
                event_id=str(uuid.uuid4()),
                doc_id=doc_id,
                run_id=run_id,
                revision=revision,
                stage=stage,
                outcome=outcome,
                started_at=started_at,
                finished_at=PipelineStageEvent.now_utc(),
                duration_ms=duration_ms,
                source=source,
                confidence=ctx["confidence"],
                error_code=ctx["error_code"],
                error_message=ctx["error_message"],
                anomaly_count=ctx["anomaly_count"],
                anomaly_max_severity=ctx["anomaly_max_severity"],
                input_bytes=ctx["input_bytes"],
                cohort_key=cohort_key,
                extra=ctx["extra"],
            )
            get_event_store().append(event)

            STAGE_DURATION_SECONDS.labels(stage.value, outcome.value, source or "n/a").observe(
                duration_ms / 1000
            )
            STAGE_EVENTS_TOTAL.labels(stage.value, outcome.value, source or "n/a").inc()
            if stage == PipelineStage.RAPIDOCR_FALLBACK:
                result_label = {
                    StageOutcome.FALLBACK_USED: "rescued",
                    StageOutcome.FAILED: "still_failed",
                    StageOutcome.SKIPPED: "disabled",
                }.get(outcome, "other")
                OCR_FALLBACK_TOTAL.labels(result_label).inc()

            logger.info(
                json.dumps(
                    {
                        "event": "pipeline_stage",
                        "doc_id": doc_id,
                        "run_id": run_id,
                        "stage": stage.value,
                        "outcome": outcome.value,
                        "duration_ms": round(duration_ms, 2),
                        "source": source,
                        "confidence": ctx["confidence"],
                        "error_code": ctx["error_code"],
                    }
                )
            )


def record_document_terminal_status(status: str) -> None:
    """Call once per document when build_report() produces a final status."""
    DOCUMENTS_PROCESSED_TOTAL.labels(status).inc()


def record_anomaly_flag(detector: str, severity: str) -> None:
    ANOMALY_FLAGS_TOTAL.labels(detector, severity).inc()
