"""Anomaly detection orchestrator — Layer 4 entry point.

Public seam: :func:`detect_anomalies`

The orchestrator is the ``StageResult -> StageResult`` step called after
``validate_record`` in the ingestion pipeline. It:

1. Skips terminal records (RED / failed validation).
2. Skips records missing ``salaire_brut`` or ``departement`` — incomplete
   records cannot participate in a salary cohort.
3. Looks up the cohort baseline for the record's ``departement``.
4. Runs each detector in :data:`DEFAULT_DETECTORS` against the salary.
5. Appends the salary to the baseline store (so future records benefit).
6. Adds anomaly flags to the ``StageResult`` — **never mutates**
   ``RecStatus`` (human-in-the-loop policy).

Hard contract (from ``AGENTS.md``):

- Anomaly detection is advisory only. The flag stream carries the
  signal; the human reviewer decides.
- A failed detector (PyOD exception, refit failure) is surfaced as a
  flag, not propagated as an exception.
"""

from __future__ import annotations

import logging
from typing import Sequence

from app.anomalies.baseline import CohortBaselineStore, get_default_baseline_store
from app.anomalies.cohort import cohort_key
from app.anomalies.detectors import _PyODDetector, make_default_detectors
from app.anomalies.result import (
    AnomalyCheckOutcome,
    flag_anomaly_baseline_insufficient,
    flag_anomaly_review_required,
)
from app.ingestion.schemas import HRRecord

logger = logging.getLogger(__name__)


def detect_anomalies(
    stage: "StageResult",
    *,
    detectors: Sequence[_PyODDetector] | None = None,
    baseline_store: CohortBaselineStore | None = None,
) -> "StageResult":
    """Run anomaly detection on a validated record.

    Parameters
    ----------
    stage:
        The ``StageResult`` coming out of ``validate_record``. Must be
        non-terminal with a populated ``record`` dict to be scored.
    detectors:
        Override the default detector list. Each detector must expose a
        ``.score(value, baseline, cohort_key) -> AnomalyResult`` method.
    baseline_store:
        Override the process-wide baseline store (for testing).

    Returns
    -------
    StageResult
        The same ``stage`` with anomaly flags appended to ``stage.flags``.
        ``RecStatus`` is never changed — anomaly detection is advisory.
    """
    # Lazy import to avoid circular dependency — StageResult lives in
    # app.ingestion.tasks which imports this module indirectly.
    from app.ingestion.tasks import StageResult

    # Pass-through: terminal records or records without a dict are not scored.
    if not isinstance(stage, StageResult) or stage.terminal or stage.record is None:
        return stage

    record_dict = stage.record
    salaire_brut = record_dict.get("salaire_brut")
    departement = record_dict.get("departement")

    # Incomplete records skip anomaly detection — they cannot contribute
    # to a salary cohort and cannot be scored against one.
    if salaire_brut is None or departement is None:
        return stage

    try:
        value = float(salaire_brut)
    except (TypeError, ValueError):
        logger.warning(
            "Skipping anomaly detection for doc_id=%s: salaire_brut=%r is not numeric",
            stage.doc_id,
            salaire_brut,
        )
        return stage

    key = cohort_key(HRRecord(**record_dict))
    if key is None:
        return stage

    store = baseline_store or get_default_baseline_store()
    active_detectors = (
        list(detectors) if detectors is not None else list(make_default_detectors())
    )

    new_flags = list(stage.flags)
    any_anomalous = False
    anomaly_results: list[dict[str, object]] = list(stage.anomaly_results)

    for detector in active_detectors:
        baseline = store.values(key)
        try:
            result = detector.score(value, baseline, key)
        except Exception as exc:  # pragma: no cover - detector-specific failure
            detector_name = getattr(detector, "name", detector.__class__.__name__).lower()
            logger.exception("Anomaly detector %s failed for doc_id=%s", detector_name, stage.doc_id)
            anomaly_results.append({
                "rule_id": f"STATISTICAL_{detector_name.upper()}_FAILED",
                "anomaly_type": "statistical",
                "severity": "WARNING",
                "document_id": stage.doc_id,
                "column_name": "salaire_brut",
                "observed_value": "[MASKED]",
                "expected_condition": "le detecteur doit produire un resultat",
                "message": f"Le detecteur {detector_name} a echoue: {type(exc).__name__}.",
                "remediation": "Verifier la configuration du detecteur et relancer l'analyse.",
                "detector": detector_name,
                "score": None,
            })
            new_flags.append(f"anomaly_detector_failed:{detector_name}")
            continue
        anomaly_results.append({
            "rule_id": f"STATISTICAL_{result.detector.upper()}",
            "anomaly_type": "statistical",
            "severity": "ERROR" if result.is_anomalous else "INFO",
            "document_id": stage.doc_id,
            "column_name": result.field,
            "observed_value": "[MASKED]",
            "expected_condition": "valeur compatible avec la distribution de la cohorte",
            "message": result.reason,
            "remediation": "Verifier le salaire et le contexte du poste avant integration.",
            "detector": result.detector,
            "score": min(1.0, abs(result.score or 0.0)),
        })

        if result.outcome is AnomalyCheckOutcome.SKIPPED:
            continue

        if result.outcome is AnomalyCheckOutcome.BASELINE_UNAVAILABLE:
            new_flags.append(
                flag_anomaly_baseline_insufficient(
                    key, store.size(key), detector._min_samples
                )
            )
            continue

        if result.is_anomalous:
            any_anomalous = True
            new_flags.append(
                flag_anomaly_review_required(result.field, result.detector)
            )

    # Append this record's salary to the baseline *after* scoring, so
    # the current record is never scored against itself.
    store.add(key, value)

    if any_anomalous:
        logger.info(
            "Anomaly detected for doc_id=%s cohort=%s — flags added",
            stage.doc_id,
            key,
        )

    return StageResult(
        doc_id=stage.doc_id,
        revision=stage.revision,
        terminal=stage.terminal,
        statut=stage.statut,
        record=stage.record,
        flags=tuple(new_flags),
        erreur_traitement=stage.erreur_traitement,
        anomaly_results=tuple(anomaly_results),
    )
