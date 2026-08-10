"""Layer 4 — statistical anomaly detection.

Public seam:

- :func:`orchestrator.detect_anomalies` — the ``StageResult -> StageResult``
  step that the ingestion pipeline calls after ``validate_record``.
- :func:`baseline.get_default_baseline_store` — process-wide in-memory
  cohort store used by the orchestrator.

Hard contract:

- Anomaly detection **never mutates** ``RecStatus``. The flag stream
  carries the anomaly signal; the human reviewer reads the score and
  reason. This is the policy locked by ``docs/runtime.md`` and
  ``AGENTS.md`` (human-in-the-loop, never auto-reject).
- A failed detector (PyOD exception, refit failure) is surfaced as a
  ``Flag`` row, not propagated as an exception. The record stays usable.
- A record without a ``departement`` or without a ``salaire_brut`` is a
  no-op for the orchestrator — incomplete records contribute nothing to
  the cohort store and receive no anomaly flag.
"""

from app.anomalies.baseline import (
    CohortBaselineStore,
    get_default_baseline_store,
    reset_default_baseline_store,
)
from app.anomalies.cohort import cohort_key
from app.anomalies.orchestrator import detect_anomalies
from app.anomalies.result import (
    AnomalyCheckOutcome,
    AnomalyResult,
    flag_anomaly_baseline_insufficient,
    flag_anomaly_review_required,
)

__all__ = [
    "AnomalyCheckOutcome",
    "AnomalyResult",
    "CohortBaselineStore",
    "cohort_key",
    "detect_anomalies",
    "flag_anomaly_baseline_insufficient",
    "flag_anomaly_review_required",
    "get_default_baseline_store",
    "reset_default_baseline_store",
]
