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
