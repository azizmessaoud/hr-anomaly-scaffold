"""Stable, privacy-conscious report projection for one uploaded document."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class AnomalyDetail(BaseModel):
    rule_id: str
    anomaly_type: str
    severity: Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
    document_id: str
    row_number: int | None = None
    column_name: str | None = None
    observed_value: Any = "[MASKED]"
    expected_condition: str
    message: str
    remediation: str
    detector: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class ReportSummary(BaseModel):
    status: Literal["ACCEPTED", "REVIEW_REQUIRED", "REJECTED", "FAILED"]
    total_rows: int = 0
    valid_rows: int = 0
    affected_rows: int = 0
    total_anomalies: int = 0
    anomalies_by_severity: dict[str, int] = Field(default_factory=dict)
    anomalies_by_rule: dict[str, int] = Field(default_factory=dict)
    anomalies_by_column: dict[str, int] = Field(default_factory=dict)


class AnalysisReport(BaseModel):
    document_id: str
    job_id: str
    processed_at: datetime
    processing_time_ms: float | None = None
    summary: ReportSummary
    anomalies: list[AnomalyDetail] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


def _severity_for_flag(flag: str) -> str:
    if flag.startswith("anomaly_review_required"):
        return "ERROR"
    if flag.startswith("validation_failed") or flag.startswith("docling_parse_failed"):
        return "CRITICAL"
    if flag.startswith("anomaly_detector_failed"):
        return "ERROR"
    return "WARNING"


def _anomaly_from_flag(document_id: str, flag: str) -> dict[str, object]:
    rule = flag.split(":", 1)[0].upper()
    severity = _severity_for_flag(flag)
    return {
        "rule_id": rule,
        "anomaly_type": "pipeline",
        "severity": severity,
        "document_id": document_id,
        "observed_value": "[MASKED]",
        "expected_condition": "respecter le contrat de traitement",
        "message": f"Signal de traitement: {rule}.",
        "remediation": "Consulter le detail du signal et corriger la source si necessaire.",
        "detector": "pipeline",
        "score": 1.0 if severity in {"ERROR", "CRITICAL"} else 0.5,
    }


class ReportRepository:
    def __init__(self) -> None:
        self._reports: dict[str, AnalysisReport] = {}

    def save(self, report: AnalysisReport) -> None:
        self._reports[report.job_id] = report

    def get(self, job_id: str) -> AnalysisReport | None:
        return self._reports.get(job_id)

    def clear(self) -> None:
        self._reports.clear()


_default_report_repository = ReportRepository()


def get_report_repository() -> ReportRepository:
    return _default_report_repository


def build_report(stage: Any) -> AnalysisReport:
    """Project a StageResult without returning the source HR record."""
    details: list[dict[str, object]] = [dict(item) for item in getattr(stage, "anomaly_results", ())]
    details.extend(_anomaly_from_flag(stage.doc_id, flag) for flag in stage.flags)
    unique: dict[tuple[object, ...], dict[str, object]] = {}
    for detail in details:
        key = (detail.get("rule_id"), detail.get("column_name"), detail.get("message"))
        unique.setdefault(key, detail)
    projected: list[AnomalyDetail] = []
    for item in list(unique.values())[:500]:
        # A detector failure has no meaningful numeric score. Preserve null
        # rather than presenting a technical failure as a measured score.
        item.setdefault("document_id", stage.doc_id)
        projected.append(AnomalyDetail(**item))
    severe = {"ERROR", "CRITICAL"}
    if stage.erreur_traitement and stage.record is None:
        status: Literal["ACCEPTED", "REVIEW_REQUIRED", "REJECTED", "FAILED"] = "FAILED"
    elif stage.statut is not None and stage.statut.value == "red":
        status = "REJECTED"
    elif any(item.severity in severe for item in projected):
        status = "REVIEW_REQUIRED" if stage.record is not None else "REJECTED"
    elif stage.statut is not None and stage.statut.value == "amber":
        status = "REVIEW_REQUIRED"
    else:
        status = "ACCEPTED"
    severity_counts = Counter(item.severity for item in projected)
    rule_counts = Counter(item.rule_id for item in projected)
    column_counts = Counter(item.column_name for item in projected if item.column_name)
    summary = ReportSummary(
        status=status,
        total_rows=1 if stage.record is not None else 0,
        valid_rows=1 if stage.record is not None and stage.statut is not None and stage.statut.value != "red" else 0,
        affected_rows=1 if projected else 0,
        total_anomalies=len(projected),
        anomalies_by_severity=dict(severity_counts),
        anomalies_by_rule=dict(rule_counts),
        anomalies_by_column=dict(column_counts),
    )
    recommendations = list(dict.fromkeys(item.remediation for item in projected))
    return AnalysisReport(
        document_id=stage.doc_id,
        job_id=stage.doc_id,
        processed_at=datetime.now(timezone.utc),
        summary=summary,
        anomalies=projected,
        recommendations=recommendations,
    )
