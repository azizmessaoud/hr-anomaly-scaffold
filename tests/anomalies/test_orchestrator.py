"""Tests for the anomaly detection orchestrator (Layer 4).

The orchestrator is the ``StageResult -> StageResult`` seam. Tests verify:

- Pass-through for terminal / incomplete records.
- Baseline insufficient flag when cohort is too small.
- Anomaly flag when detector scores a salary as anomalous.
- No anomaly flag when salary is within normal range.
- No mutation of ``RecStatus`` — anomaly detection is advisory only.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.anomalies.baseline import CohortBaselineStore
from app.anomalies.orchestrator import detect_anomalies
from app.anomalies.result import AnomalyCheckOutcome, AnomalyResult, MIN_COHORT_SIZE
from app.ingestion.schemas import RecStatus
from app.ingestion.tasks import StageResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage(
    *,
    doc_id: str = "doc-1",
    salaire_brut: float = 5000.0,
    departement: str = "IT",
    statut: RecStatus = RecStatus.GREEN,
    terminal: bool = False,
    flags: tuple[str, ...] = (),
) -> StageResult:
    record = {
        "id": doc_id,
        "revision": 1,
        "nom": "Dupont",
        "prenom": "Jean",
        "cin": "AB123456",
        "cnss": "123456789",
        "date_embauche": "2020-01-15",
        "salaire_brut": salaire_brut,
        "poste": "Developpeur",
        "departement": departement,
        "confiance": 0.9,
        "statut": statut,
    }
    return StageResult(
        doc_id=doc_id,
        revision=1,
        terminal=terminal,
        statut=statut,
        record=record,
        flags=flags,
    )


def _mock_detector(name: str = "test_detector", anomalous: bool = False):
    """Return a mock detector that always scores the same way.

    The mock's ``score()`` returns a fixed outcome regardless of baseline.
    For the baseline-insufficient test, use ``_mock_baseline_insufficient_detector``.
    """
    detector = MagicMock()
    detector.name = name
    detector._min_samples = MIN_COHORT_SIZE
    detector.score.return_value = AnomalyResult(
        detector=name,
        field="salaire_brut",
        cohort_key=("IT",),
        score=-0.5 if anomalous else 0.5,
        outcome=AnomalyCheckOutcome.ANOMALOUS if anomalous else AnomalyCheckOutcome.NOT_ANOMALOUS,
        reason=f"test: {'anomalous' if anomalous else 'normal'}",
    )
    return detector


def _mock_baseline_insufficient_detector(name: str = "test_detector"):
    """Return a mock detector that returns BASELINE_UNAVAILABLE."""
    detector = MagicMock()
    detector.name = name
    detector._min_samples = MIN_COHORT_SIZE
    detector.score.return_value = AnomalyResult(
        detector=name,
        field="salaire_brut",
        cohort_key=("IT",),
        score=None,
        outcome=AnomalyCheckOutcome.BASELINE_UNAVAILABLE,
        reason="baseline too small",
    )
    return detector


def test_detector_failure_is_reported_without_aborting_pipeline():
    """A detector failure is reviewer-visible and does not block ingestion."""
    store = CohortBaselineStore()
    detector = MagicMock()
    detector.name = "broken_detector"
    detector._min_samples = MIN_COHORT_SIZE
    detector.score.side_effect = RuntimeError("model unavailable")

    result = detect_anomalies(_make_stage(), detectors=[detector], baseline_store=store)

    assert "anomaly_detector_failed:broken_detector" in result.flags
    assert result.statut == RecStatus.GREEN
    assert result.erreur_traitement is None
    assert result.anomaly_results[-1]["severity"] == "WARNING"
    assert store.size(("IT",)) == 1


# ---------------------------------------------------------------------------
# Pass-through tests
# ---------------------------------------------------------------------------


def test_terminal_stage_passes_through():
    """Terminal stages (RED / failed) are not scored."""
    stage = _make_stage(terminal=True)
    result = detect_anomalies(stage)
    assert result is stage


def test_no_record_passes_through():
    """Stages without a record dict are not scored."""
    stage = StageResult(doc_id="doc-1", revision=1, terminal=False)
    result = detect_anomalies(stage)
    assert result is stage


def test_missing_salaire_brut_passes_through():
    """Records without salaire_brut skip anomaly detection."""
    stage = _make_stage()
    stage.record.pop("salaire_brut")
    result = detect_anomalies(stage)
    assert result is stage


def test_missing_departement_passes_through():
    """Records without departement skip anomaly detection."""
    stage = _make_stage()
    stage.record.pop("departement")
    result = detect_anomalies(stage)
    assert result is stage


def test_non_numeric_salaire_brut_passes_through():
    """Records with non-numeric salaire_brut skip anomaly detection."""
    stage = _make_stage()
    stage.record["salaire_brut"] = "not-a-number"
    result = detect_anomalies(stage)
    assert result is stage


# ---------------------------------------------------------------------------
# Baseline insufficient
# ---------------------------------------------------------------------------


def test_baseline_insufficient_adds_flag():
    """When the cohort has fewer than MIN_COHORT_SIZE records, the
    baseline_insufficient flag is added and no anomaly flag is emitted."""
    store = CohortBaselineStore()
    # Empty store — 0 samples, below MIN_COHORT_SIZE
    detector = _mock_baseline_insufficient_detector()
    stage = _make_stage()

    result = detect_anomalies(stage, detectors=[detector], baseline_store=store)

    flag_names = [f.split(":")[0] for f in result.flags]
    assert "anomaly_baseline_insufficient" in flag_names
    assert not any("anomaly_review_required" in f for f in result.flags)
    # Salary should still be appended to the store
    assert store.size(("IT",)) == 1


# ---------------------------------------------------------------------------
# Anomalous salary
# ---------------------------------------------------------------------------


def test_anomalous_salary_adds_review_flag():
    """When a detector flags the salary as anomalous, the
    anomaly_review_required flag is added."""
    store = CohortBaselineStore()
    # Pre-populate with enough samples
    for v in [4000, 4200, 4100, 4300, 4400, 4500, 4600, 4700, 4800, 4900]:
        store.add(("IT",), v)

    detector = _mock_detector(anomalous=True)
    stage = _make_stage(salaire_brut=15000.0)

    result = detect_anomalies(stage, detectors=[detector], baseline_store=store)

    assert any("anomaly_review_required" in f for f in result.flags)
    assert store.size(("IT",)) == 11  # 10 + 1 new


def test_normal_salary_no_anomaly_flag():
    """When the detector does not flag the salary, no review flag is added."""
    store = CohortBaselineStore()
    for v in [4000, 4200, 4100, 4300, 4400, 4500, 4600, 4700, 4800, 4900]:
        store.add(("IT",), v)

    detector = _mock_detector(anomalous=False)
    stage = _make_stage(salaire_brut=4500.0)

    result = detect_anomalies(stage, detectors=[detector], baseline_store=store)

    assert not any("anomaly_review_required" in f for f in result.flags)
    assert store.size(("IT",)) == 11


# ---------------------------------------------------------------------------
# RecStatus never mutated
# ---------------------------------------------------------------------------


def test_recstatus_never_mutated():
    """Anomaly detection must never change RecStatus — it is advisory only."""
    store = CohortBaselineStore()
    for v in [4000, 4200, 4100, 4300, 4400, 4500, 4600, 4700, 4800, 4900]:
        store.add(("IT",), v)

    detector = _mock_detector(anomalous=True)
    stage = _make_stage(salaire_brut=15000.0, statut=RecStatus.GREEN)

    result = detect_anomalies(stage, detectors=[detector], baseline_store=store)

    assert result.statut == RecStatus.GREEN


# ---------------------------------------------------------------------------
# Multiple detectors
# ---------------------------------------------------------------------------


def test_multiple_detectors_both_anomalous():
    """When multiple detectors flag the salary, multiple review flags appear."""
    store = CohortBaselineStore()
    for v in [4000, 4200, 4100, 4300, 4400, 4500, 4600, 4700, 4800, 4900]:
        store.add(("IT",), v)

    d1 = _mock_detector(name="iforest", anomalous=True)
    d2 = _mock_detector(name="ecod", anomalous=True)
    stage = _make_stage(salaire_brut=15000.0)

    result = detect_anomalies(stage, detectors=[d1, d2], baseline_store=store)

    review_flags = [f for f in result.flags if "anomaly_review_required" in f]
    assert len(review_flags) == 2


def test_one_anomalous_one_normal():
    """When one detector flags and another doesn't, only one review flag appears."""
    store = CohortBaselineStore()
    for v in [4000, 4200, 4100, 4300, 4400, 4500, 4600, 4700, 4800, 4900]:
        store.add(("IT",), v)

    d1 = _mock_detector(name="iforest", anomalous=True)
    d2 = _mock_detector(name="ecod", anomalous=False)
    stage = _make_stage(salaire_brut=15000.0)

    result = detect_anomalies(stage, detectors=[d1, d2], baseline_store=store)

    review_flags = [f for f in result.flags if "anomaly_review_required" in f]
    assert len(review_flags) == 1
    assert "iforest" in review_flags[0]


# ---------------------------------------------------------------------------
# Existing flags preserved
# ---------------------------------------------------------------------------


def test_existing_flags_preserved():
    """Anomaly flags are additive — existing extractor flags are kept."""
    store = CohortBaselineStore()
    for v in [4000, 4200, 4100, 4300, 4400, 4500, 4600, 4700, 4800, 4900]:
        store.add(("IT",), v)

    detector = _mock_detector(anomalous=True)
    stage = _make_stage(flags=("rapidocr_fallback", "low_confidence"))

    result = detect_anomalies(stage, detectors=[detector], baseline_store=store)

    assert "rapidocr_fallback" in result.flags
    assert "low_confidence" in result.flags
    assert any("anomaly_review_required" in f for f in result.flags)
