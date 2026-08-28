"""PyOD-backed detectors for Layer 4.

Two unsupervised detectors ship in MVP:

- :class:`IsolationForestDetector` — Isolation Forest. Contamination
  defaults to ``0.1``; ``random_state=42`` keeps the test suite
  deterministic. ``n_estimators`` is left at PyOD's default (100).
- :class:`ECODDetector` — ECOD (Empirical Cumulative Distribution
  Functions for Outlier Detection). Parameter-free and stable on
  small cohorts, which is why it is preferred over COPOD at MVP.

Each detector is a thin object with two responsibilities: fit a PyOD
model lazily on the first ``score`` call (cache the fit), and convert
the model's internal score to a stable, comparable ``AnomalyResult``.

The detectors never raise. Internal PyOD exceptions are caught and
returned as an :class:`AnomalyResult` with
``outcome=BASELINE_UNAVAILABLE`` so the orchestrator can keep producing
a valid :class:`StageResult`.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.anomalies.result import (
    AnomalyCheckOutcome,
    AnomalyResult,
    MIN_COHORT_SIZE,
)

logger = logging.getLogger(__name__)


def _cohort_label(cohort_key: tuple[str, ...]) -> str:
    return ",".join(cohort_key) or "<unknown>"


def _baseline_unavailable(
    *,
    detector: str,
    field: str,
    cohort_key: tuple[str, ...],
    reason: str,
) -> AnomalyResult:
    return AnomalyResult(
        detector=detector,
        field=field,
        cohort_key=cohort_key,
        score=None,
        outcome=AnomalyCheckOutcome.BASELINE_UNAVAILABLE,
        reason=reason,
    )


class _PyODDetector:
    """Shared base for PyOD-backed detectors.

    Subclasses implement :meth:`_build_model` (must produce an
    estimator with sklearn-style ``fit``/``decision_function``) and
    :meth:`_format_reason` (build the free-text explanation).

    Caching strategy: the PyOD model is refit whenever the baseline
    length changes. With small per-department cohorts (typical salary
    distributions of 10–100 records), the refit cost is negligible and
    the discipline of "model always matches the latest baseline" is
    worth keeping simple. Avoids the global-state footgun flagged in
    the planning notes.
    """

    name: str = ""
    field: str = "salaire_brut"

    def __init__(self, min_samples: int = MIN_COHORT_SIZE) -> None:
        self._min_samples = min_samples
        self._model = None
        self._fitted_size: Optional[int] = None

    # -- subclass hooks ---------------------------------------------------
    def _build_model(self):  # pragma: no cover - trivial override
        raise NotImplementedError

    def _format_reason(self, value: float, score: float) -> str:
        return (
            f"{self.name} scored {value:.2f} at score {score:+.3f} "
            f"(more negative = more anomalous)"
        )

    # -- public -----------------------------------------------------------
    def score(
        self,
        value: float,
        baseline: list[float],
        cohort_key: tuple[str, ...],
    ) -> AnomalyResult:
        baseline_size = len(baseline)
        cohort_label = _cohort_label(cohort_key)

        if baseline_size < self._min_samples:
            return _baseline_unavailable(
                detector=self.name,
                field=self.field,
                cohort_key=cohort_key,
                reason=(
                    f"baseline cohort '{cohort_label}' has {baseline_size} "
                    f"samples; minimum {self._min_samples} required"
                ),
            )

        try:
            self._refit_if_needed(baseline)
            score = float(self._model.decision_function([[float(value)]])[0])
        except Exception as exc:  # pragma: no cover - exception path is uniform
            logger.warning(
                "%s detector failed for cohort=%s value=%s: %s",
                self.name,
                cohort_label,
                value,
                exc,
            )
            return _baseline_unavailable(
                detector=self.name,
                field=self.field,
                cohort_key=cohort_key,
                reason=f"{self.name} internal failure: {type(exc).__name__}",
            )

        outcome = (
            AnomalyCheckOutcome.ANOMALOUS
            if self._is_anomalous(score)
            else AnomalyCheckOutcome.NOT_ANOMALOUS
        )
        return AnomalyResult(
            detector=self.name,
            field=self.field,
            cohort_key=cohort_key,
            score=score,
            outcome=outcome,
            reason=self._format_reason(value, score),
        )

    # -- internal ---------------------------------------------------------
    def _refit_if_needed(self, baseline: list[float]) -> None:
        if (
            self._model is None
            or self._fitted_size != len(baseline)
        ):
            self._model = self._build_model()
            self._model.fit(_matrix(baseline))
            self._fitted_size = len(baseline)

    def _is_anomalous(self, score: float) -> bool:
        """PyOD convention: more negative score = more anomalous.

        Both Isolation Forest and ECOD follow this convention
        (``decision_function`` returns the opposite sign of an
        anomaly score). Threshold 0 separates "predicted inlier" from
        "predicted outlier" — using PyOD's own threshold keeps the
        decision boundary consistent with how each detector trains.
        """
        return score < 0


def _matrix(values: list[float]):
    """Build a (n, 1) ndarray from a flat list of scalars.

    Isolated to one helper so PyOD's 2-D shape requirement is in a
    single place. ``numpy`` is a transitive dep of PyOD so it is
    available wherever this module imports.
    """
    import numpy as np

    return np.asarray(values, dtype=float).reshape(-1, 1)


class IsolationForestDetector(_PyODDetector):
    """Isolation Forest wrapper.

    ``contamination`` is the prior fraction of outliers assumed in the
    cohort. ``0.1`` is PyOD's default and the right choice for HR
    salary distributions where a small but non-trivial tail of
    high-earning outliers is normal (sales bonuses, exec grades, etc.).
    """

    name = "isolation_forest"

    def _build_model(self):
        from pyod.models.iforest import IForest

        return IForest(contamination=0.1, random_state=42)

    def _format_reason(self, value: float, score: float) -> str:
        return (
            f"Isolation Forest flagged salaire_brut={value:.2f} "
            f"as anomalous for department cohort (decision_function={score:+.3f})"
        )


class ECODDetector(_PyODDetector):
    """ECOD wrapper.

    Parameter-free; PyOD's ECOD does not expose ``contamination`` and
    infers the threshold from the empirical CDF. Stable on small
    cohorts — preferred over COPOD for HR data per architecture doc.
    """

    name = "ecod"

    def _build_model(self):
        from pyod.models.ecod import ECOD

        return ECOD()

    def _format_reason(self, value: float, score: float) -> str:
        return (
            f"ECOD flagged salaire_brut={value:.2f} as a tail outlier "
            f"for department cohort (decision_function={score:+.3f})"
        )


def make_default_detectors() -> tuple[_PyODDetector, ...]:
    """Return fresh instances for one anomaly-detection invocation."""
    return IsolationForestDetector(), ECODDetector()


# Public detector instances retained for compatibility with callers that
# inspect the default set. The orchestrator uses the factory above so fitted
# model state is not shared between documents or cohorts.
DEFAULT_DETECTORS: tuple[_PyODDetector, ...] = make_default_detectors()
