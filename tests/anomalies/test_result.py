"""Tests for Layer 4 result types and flag vocabulary."""

from __future__ import annotations

from app.anomalies.result import (
    AnomalyCheckOutcome,
    AnomalyResult,
    flag_anomaly_baseline_insufficient,
    flag_anomaly_review_required,
)


def test_anomaly_result_is_anomalous():
    r = AnomalyResult(
        detector="iforest",
        field="salaire_brut",
        cohort_key=("IT",),
        score=-0.5,
        outcome=AnomalyCheckOutcome.ANOMALOUS,
        reason="test",
    )
    assert r.is_anomalous is True


def test_anomaly_result_not_anomalous():
    r = AnomalyResult(
        detector="iforest",
        field="salaire_brut",
        cohort_key=("IT",),
        score=0.5,
        outcome=AnomalyCheckOutcome.NOT_ANOMALOUS,
        reason="test",
    )
    assert r.is_anomalous is False


def test_flag_anomaly_review_required_format():
    flag = flag_anomaly_review_required("salaire_brut", "iforest")
    assert flag == "anomaly_review_required:salaire_brut:iforest"


def test_flag_anomaly_baseline_insufficient_format():
    flag = flag_anomaly_baseline_insufficient(("IT",), 5, 10)
    assert flag == "anomaly_baseline_insufficient:IT:5:10"


def test_flag_anomaly_baseline_insufficient_unknown_cohort():
    flag = flag_anomaly_baseline_insufficient((), 3, 10)
    assert flag == "anomaly_baseline_insufficient:<unknown>:3:10"


def test_anomaly_check_outcome_values():
    assert AnomalyCheckOutcome.ANOMALOUS == "anomalous"
    assert AnomalyCheckOutcome.NOT_ANOMALOUS == "not_anomalous"
    assert AnomalyCheckOutcome.BASELINE_UNAVAILABLE == "baseline_unavailable"
    assert AnomalyCheckOutcome.SKIPPED == "skipped"
