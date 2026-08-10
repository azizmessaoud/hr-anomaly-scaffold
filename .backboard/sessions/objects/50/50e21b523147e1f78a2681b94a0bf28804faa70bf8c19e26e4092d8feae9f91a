"""Result types and canonical flag vocabulary for Layer 4.

Mirrors :mod:`app.ingestion.extraction_result` — the orchestrator-level
flag stream stays string-shaped and additive (no compound names), and
each ``AnomalyResult`` carries both a numeric score and a free-text
``reason`` so the dashboard can render an explainable signal.

Flag string grammar (additive, parseable, never compound):

- ``anomaly_review_required`` — orchestrator-level signal that at least
  one detector flagged the record. Reviewer should inspect.
- ``anomaly_baseline_insufficient:<cohort>:<n>:<min_required>`` —
  cohort has fewer than ``min_required`` validated records; no score
  emitted. Reviewer should accept the record and grow the cohort.
- ``anomaly_salary:<detector>:<score>:<cohort>`` — record-level raw
  score from a single detector, used for diagnostic grouping only;
  normal reviewer decisions are driven by the
  ``anomaly_review_required`` orchestrator signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Minimum cohort size before any detector runs. Below this, anomaly
# detection emits ``anomaly_baseline_insufficient`` and no score.
# Isolation Forest needs roughly 10 samples for a stable fit; ECOD is
# parameter-free but still needs at least 5 to give a non-degenerate
# distribution. 10 is a conservative default.
MIN_COHORT_SIZE: int = 10


class AnomalyCheckOutcome(str, Enum):
    """Classification of a single detector's verdict on one record.

    Distinct from ``RecStatus`` — anomaly outcomes never promote
    records upward in the status taxonomy. The orchestrator surfaces
    the outcome as a flag and leaves ``RecStatus`` untouched.
    """

    ANOMALOUS = "anomalous"
    NOT_ANOMALOUS = "not_anomalous"
    BASELINE_UNAVAILABLE = "baseline_unavailable"
    SKIPPED = "skipped"  # record lacks required fields for this detector


@dataclass(frozen=True)
class AnomalyResult:
    """One detector's verdict on one record.

    Always carries both a numeric ``score`` and a free-text ``reason``
    per ``docs/architecture.md``: a bare score without a justification
    is forbidden — the reviewer dashboard renders the reason as the
    primary signal and uses the score only for ordering / drill-down.
    """

    detector: str
    field: str
    cohort_key: tuple[str, ...]
    score: Optional[float]
    outcome: AnomalyCheckOutcome
    reason: str

    @property
    def is_anomalous(self) -> bool:
        return self.outcome is AnomalyCheckOutcome.ANOMALOUS


def flag_anomaly_review_required(field: str, detector: str) -> str:
    """Orchestrator-level flag fired when a detector flagged the record.

    The :class:`Flag` projector in :mod:`app.ingestion.job_state` maps
    this bare string into ``Flag(moteur="pipeline", detail=<flag>)``,
    so the dashboard grouping bucket for anomalies is independent of
    which detector produced the signal.

    The ``field`` and ``detector`` qualifiers are appended additively —
    multiple calls produce multiple flags, never a compound name.
    """
    return f"anomaly_review_required:{field}:{detector}"


def flag_anomaly_baseline_insufficient(
    cohort_key: tuple[str, ...],
    cohort_size: int,
    min_required: int = MIN_COHORT_SIZE,
) -> str:
    """Flag fired when the cohort has fewer than ``min_required`` records.

    Carries the cohort key, current size, and required minimum so the
    reviewer can see exactly how much data is missing for a reliable
    anomaly call. Format is strict, parseable, and additive.
    """
    cohort_label = ",".join(cohort_key) or "<unknown>"
    return (
        f"anomaly_baseline_insufficient:{cohort_label}:"
        f"{cohort_size}:{min_required}"
    )
