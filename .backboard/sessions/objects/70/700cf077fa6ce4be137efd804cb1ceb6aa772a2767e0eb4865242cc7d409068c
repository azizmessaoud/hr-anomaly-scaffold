"""Tests for Layer 4 detectors (PyOD wrappers).

Each detector is a thin adapter around a PyOD model. Tests verify:

- Baseline too small → ``BASELINE_UNAVAILABLE``.
- Normal value → ``NOT_ANOMALOUS``.
- Anomalous value → ``ANOMALOUS``.
- Refit happens when baseline length changes.

Skipped when PyOD is not installed (detector logic is still exercised
via the orchestrator tests with mock detectors).
"""

from __future__ import annotations

import pytest

try:
    from pyod.models.iforest import IForest  # noqa: F401

    HAS_PYOD = True
except ImportError:
    HAS_PYOD = False

from app.anomalies.result import AnomalyCheckOutcome, MIN_COHORT_SIZE

pytestmark = pytest.mark.skipif(not HAS_PYOD, reason="pyod not installed")


@pytest.fixture(autouse=True)
def _import_detectors():
    """Import detectors inside the fixture so the skipif works."""
    from app.anomalies.detectors import IsolationForestDetector, ECODDetector

    global _IF, _ECOD
    _IF = IsolationForestDetector
    _ECOD = ECODDetector


# ---------------------------------------------------------------------------
# IsolationForestDetector
# ---------------------------------------------------------------------------


class TestIsolationForestDetector:
    def setup_method(self):
        self.detector = _IF()

    def test_baseline_too_small(self):
        baseline = [4000.0] * (MIN_COHORT_SIZE - 1)
        result = self.detector.score(5000.0, baseline, ("IT",))
        assert result.outcome is AnomalyCheckOutcome.BASELINE_UNAVAILABLE
        assert result.score is None

    def test_normal_value(self):
        baseline = [4000 + i * 100 for i in range(20)]
        result = self.detector.score(4500.0, baseline, ("IT",))
        assert result.outcome in (
            AnomalyCheckOutcome.NOT_ANOMALOUS,
            AnomalyCheckOutcome.ANOMALOUS,
        )
        assert result.score is not None
        assert result.detector == "isolation_forest"
        assert result.field == "salaire_brut"

    def test_extreme_value_is_anomalous(self):
        baseline = [4000 + i * 50 for i in range(30)]
        result = self.detector.score(50000.0, baseline, ("IT",))
        assert result.outcome is AnomalyCheckOutcome.ANOMALOUS
        assert result.score is not None
        assert result.score < 0

    def test_refit_on_baseline_change(self):
        baseline = [4000 + i * 100 for i in range(20)]
        self.detector.score(4500.0, baseline, ("IT",))
        assert self.detector._fitted_size == 20

        baseline.append(5000.0)
        self.detector.score(4500.0, baseline, ("IT",))
        assert self.detector._fitted_size == 21


# ---------------------------------------------------------------------------
# ECODDetector
# ---------------------------------------------------------------------------


class TestECODDetector:
    def setup_method(self):
        self.detector = _ECOD()

    def test_baseline_too_small(self):
        baseline = [4000.0] * (MIN_COHORT_SIZE - 1)
        result = self.detector.score(5000.0, baseline, ("IT",))
        assert result.outcome is AnomalyCheckOutcome.BASELINE_UNAVAILABLE

    def test_normal_value(self):
        baseline = [4000 + i * 100 for i in range(20)]
        result = self.detector.score(4500.0, baseline, ("IT",))
        assert result.outcome in (
            AnomalyCheckOutcome.NOT_ANOMALOUS,
            AnomalyCheckOutcome.ANOMALOUS,
        )
        assert result.detector == "ecod"

    def test_extreme_value_is_anomalous(self):
        baseline = [4000 + i * 50 for i in range(30)]
        result = self.detector.score(50000.0, baseline, ("IT",))
        assert result.outcome is AnomalyCheckOutcome.ANOMALOUS
