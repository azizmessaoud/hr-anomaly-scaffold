"""Deterministic, explainable HR data-quality rules.

This module intentionally returns data rather than raising domain errors. A
technical failure (for example, an unavailable extractor) is handled by the
ingestion task; malformed HR values are represented as anomaly details.
"""

from __future__ import annotations

from datetime import date
from typing import Any


SENSITIVE_COLUMNS = frozenset({"nom", "prenom", "email", "telephone", "cin", "cnss", "salaire_brut"})


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _anomaly(
    *,
    rule_id: str,
    severity: str,
    column_name: str | None,
    expected_condition: str,
    message: str,
    remediation: str,
    observed_value: Any = None,
) -> dict[str, object]:
    exposed = "[MASKED]" if column_name in SENSITIVE_COLUMNS else observed_value
    if observed_value is None and exposed is None:
        exposed = "[MASKED]"
    return {
        "rule_id": rule_id,
        "anomaly_type": "validation",
        "severity": severity,
        "column_name": column_name,
        "observed_value": exposed,
        "expected_condition": expected_condition,
        "message": message,
        "remediation": remediation,
        "detector": "deterministic_validation",
        "score": 1.0 if severity in {"ERROR", "CRITICAL"} else 0.5,
    }


def validate_hr_record(payload: dict[str, Any]) -> list[dict[str, object]]:
    """Return deterministic anomalies for the fields available in HRRecord."""
    anomalies: list[dict[str, object]] = []
    required = ("nom", "cin", "cnss", "date_embauche", "salaire_brut")
    for field in required:
        if _blank(payload.get(field)):
            anomalies.append(
                _anomaly(
                    rule_id="REQUIRED_VALUE_MISSING",
                    severity="ERROR",
                    column_name=field,
                    expected_condition=f"{field} doit etre renseigne",
                    message=f"La valeur obligatoire {field} est absente ou vide.",
                    remediation=f"Renseigner la colonne {field} avant integration.",
                )
            )

    date_fields = ("date_embauche", "date_sortie", "date_naissance")
    parsed: dict[str, date] = {}
    for field in date_fields:
        value = payload.get(field)
        if _blank(value):
            continue
        try:
            parsed[field] = date.fromisoformat(str(value).strip())
        except ValueError:
            anomalies.append(
                _anomaly(
                    rule_id="DATE_INVALID",
                    severity="ERROR",
                    column_name=field,
                    observed_value=value,
                    expected_condition="date ISO valide YYYY-MM-DD",
                    message=f"La date {field} est invalide.",
                    remediation=f"Corriger {field} au format YYYY-MM-DD.",
                )
            )

    if "date_embauche" in parsed and "date_sortie" in parsed and parsed["date_sortie"] < parsed["date_embauche"]:
        anomalies.append(
            _anomaly(
                rule_id="DATE_ORDER_INVALID",
                severity="ERROR",
                column_name="date_sortie",
                observed_value=payload.get("date_sortie"),
                expected_condition="date_sortie >= date_embauche",
                message="La date de sortie est anterieure a la date d'embauche.",
                remediation="Corriger la date de sortie ou verifier la date d'embauche.",
            )
        )
    if "date_naissance" in parsed and parsed["date_naissance"] > date.today():
        anomalies.append(
            _anomaly(
                rule_id="BIRTH_DATE_IN_FUTURE",
                severity="ERROR",
                column_name="date_naissance",
                expected_condition="date_naissance <= date du traitement",
                message="La date de naissance est dans le futur.",
                remediation="Verifier la date de naissance saisie.",
            )
        )

    salary = payload.get("salaire_brut")
    if salary is not None:
        try:
            if float(salary) < 0:
                anomalies.append(
                    _anomaly(
                        rule_id="SALARY_NEGATIVE",
                        severity="ERROR",
                        column_name="salaire_brut",
                        expected_condition="salaire_brut >= 0",
                        message="Le salaire brut est negatif.",
                        remediation="Corriger le montant du salaire brut.",
                    )
                )
        except (TypeError, ValueError):
            anomalies.append(
                _anomaly(
                    rule_id="NUMERIC_CONVERSION_FAILED",
                    severity="ERROR",
                    column_name="salaire_brut",
                    expected_condition="valeur numerique convertible",
                    message="Le salaire brut n'est pas numerique.",
                    remediation="Utiliser un nombre et un separateur decimal coherent.",
                )
            )

    status = str(payload.get("statut_employe", "")).strip().lower()
    if status and status not in {"actif", "inactif", "active", "inactive", "terminated", "leave"}:
        anomalies.append(
            _anomaly(
                rule_id="CATEGORY_UNKNOWN",
                severity="WARNING",
                column_name="statut_employe",
                expected_condition="statut_employe dans le referentiel configure",
                message="Le statut employe est inconnu.",
                remediation="Utiliser une valeur du referentiel RH.",
            )
        )
    if status in {"actif", "active"} and parsed.get("date_sortie") is not None:
        anomalies.append(
            _anomaly(
                rule_id="ACTIVE_WITH_EXIT_DATE",
                severity="WARNING",
                column_name="date_sortie",
                expected_condition="un employe actif ne doit pas avoir de date de sortie",
                message="Un employe actif possede une date de sortie.",
                remediation="Verifier le statut et la date de sortie.",
            )
        )
    hours = payload.get("heures_hebdomadaires")
    if hours is not None:
        try:
            if float(hours) < 0 or float(hours) > 168:
                anomalies.append(
                    _anomaly(
                        rule_id="WORKING_HOURS_OUT_OF_RANGE",
                        severity="ERROR",
                        column_name="heures_hebdomadaires",
                        expected_condition="0 <= heures_hebdomadaires <= 168",
                        message="Le nombre d'heures hebdomadaires est impossible.",
                        remediation="Corriger le temps de travail.",
                    )
                )
        except (TypeError, ValueError):
            anomalies.append(
                _anomaly(
                    rule_id="NUMERIC_CONVERSION_FAILED",
                    severity="ERROR",
                    column_name="heures_hebdomadaires",
                    expected_condition="valeur numerique convertible",
                    message="Les heures hebdomadaires ne sont pas numeriques.",
                    remediation="Corriger le format du temps de travail.",
                )
            )
    return anomalies
