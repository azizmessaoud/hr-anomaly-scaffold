from app.pipeline.data_validation import validate_hr_record


def test_required_spaces_are_reported_and_sensitive_values_are_masked():
    anomalies = validate_hr_record({"nom": "  ", "cin": None, "cnss": None})
    assert {item["column_name"] for item in anomalies} >= {"nom", "cin", "cnss"}
    assert all(item["observed_value"] == "[MASKED]" for item in anomalies)


def test_date_order_salary_and_hours_rules():
    anomalies = validate_hr_record(
        {
            "nom": "Employee",
            "cin": "AB123456",
            "cnss": "123456789",
            "date_embauche": "2024-01-01",
            "date_sortie": "2023-01-01",
            "salaire_brut": -1,
            "heures_hebdomadaires": 200,
        }
    )
    rules = {item["rule_id"] for item in anomalies}
    assert {"DATE_ORDER_INVALID", "SALARY_NEGATIVE", "WORKING_HOURS_OUT_OF_RANGE"} <= rules


def test_missing_optional_employee_status_is_not_an_unknown_category():
    anomalies = validate_hr_record({"nom": "Employee"})

    assert "CATEGORY_UNKNOWN" not in {item["rule_id"] for item in anomalies}


def test_detector_failure_can_be_projected_into_a_report():
    from app.pipeline.report import build_report

    class FailedStage:
        doc_id = "doc-x"
        statut = type("Status", (), {"value": "green"})()
        record = {"id": "doc-x"}
        flags = ("anomaly_detector_failed:ecod",)
        erreur_traitement = None
        anomaly_results = ({
            "rule_id": "STATISTICAL_ECOD_FAILED",
            "anomaly_type": "statistical",
            "severity": "WARNING",
            "document_id": "doc-x",
            "column_name": "salaire_brut",
            "observed_value": "[MASKED]",
            "expected_condition": "le detecteur doit produire un resultat",
            "message": "Le detecteur ecod a echoue.",
            "remediation": "Verifier la configuration du detecteur.",
            "detector": "ecod",
            "score": None,
        },)

    report = build_report(FailedStage())

    assert report.summary.status == "REVIEW_REQUIRED"
    assert report.anomalies[0].score is None


def test_non_finite_numeric_values_are_anomalies():
    for value in (float("nan"), float("inf")):
        anomalies = validate_hr_record(
            {
                "nom": "Employee",
                "cin": "AB123456",
                "cnss": "123456789",
                "date_embauche": "2024-01-01",
                "salaire_brut": value,
            }
        )
        assert "NUMERIC_NOT_FINITE" in {item["rule_id"] for item in anomalies}
