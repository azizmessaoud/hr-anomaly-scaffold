"""Durable, append-only store for PipelineStageEvent, and the API projections
built on top of it.

STAR — Result: this store is what makes observability *queryable* rather
than just "grep the logs". SQLite is the default so the demo mode stays
dependency-free (matches the base repo's "no Redis/Postgres required"
stance); swap the DSN for PostgreSQL when RUNTIME_MODE=full without
changing any call site.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from app.observability.schemas import PipelineRunSummary, PipelineStage, PipelineStageEvent

_DB_PATH = Path("outputs/observability.db")
_lock = threading.Lock()


class EventStore:
    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_stage_events (
                    event_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    source TEXT,
                    confidence REAL,
                    error_code TEXT,
                    error_message TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    anomaly_count INTEGER,
                    anomaly_max_severity TEXT,
                    input_bytes INTEGER,
                    cohort_key TEXT,
                    extra_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_run_id ON pipeline_stage_events(run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_doc_id ON pipeline_stage_events(doc_id)"
            )

    def append(self, event: PipelineStageEvent) -> None:
        with _lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_stage_events VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event.event_id,
                    event.doc_id,
                    event.run_id,
                    event.revision,
                    event.stage.value,
                    event.outcome.value,
                    event.started_at.isoformat(),
                    event.finished_at.isoformat(),
                    event.duration_ms,
                    event.source,
                    event.confidence,
                    event.error_code,
                    event.error_message,
                    event.retry_count,
                    event.anomaly_count,
                    event.anomaly_max_severity,
                    event.input_bytes,
                    event.cohort_key,
                    json.dumps(event.extra),
                ),
            )

    def get_run_events(self, run_id: str) -> list[PipelineStageEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pipeline_stage_events WHERE run_id = ? ORDER BY started_at",
                (run_id,),
            ).fetchall()
        cols = [
            "event_id", "doc_id", "run_id", "revision", "stage", "outcome",
            "started_at", "finished_at", "duration_ms", "source", "confidence",
            "error_code", "error_message", "retry_count", "anomaly_count",
            "anomaly_max_severity", "input_bytes", "cohort_key", "extra_json",
        ]
        events = []
        for row in rows:
            payload = dict(zip(cols, row))
            payload["extra"] = json.loads(payload.pop("extra_json"))
            events.append(PipelineStageEvent(**payload))
        return events

    def get_run_summary(self, run_id: str, final_status: str) -> Optional[PipelineRunSummary]:
        events = self.get_run_events(run_id)
        if not events:
            return None
        total_duration = sum(e.duration_ms for e in events)
        bottleneck = max(events, key=lambda e: e.duration_ms).stage
        ocr_used = any(
            e.stage == PipelineStage.RAPIDOCR_FALLBACK and e.outcome.value == "fallback_used"
            for e in events
        )
        return PipelineRunSummary(
            doc_id=events[0].doc_id,
            run_id=run_id,
            revision=events[0].revision,
            total_duration_ms=total_duration,
            stages=events,
            final_status=final_status,  # type: ignore[arg-type]
            ocr_fallback_used=ocr_used,
            bottleneck_stage=bottleneck,
        )


_default_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    global _default_store
    if _default_store is None:
        _default_store = EventStore()
    return _default_store
