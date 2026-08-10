"""Tests for the canonical flag vocabulary defined in extraction_result.py.

The flag helpers are additive: each is a small string the orchestrator
can attach to the StageResult. The string shape is part of the public
contract surfaced on the API, so a typo or accidental rename would
break downstream consumers (review dashboard, audit log, alerting).
"""
from __future__ import annotations

from app.ingestion.extraction_result import (
    flag_docling_low_confidence_review,
    flag_low_confidence,
    flag_missing_fields,
    flag_rapidocr_disabled_in_env,
    flag_rapidocr_fallback,
    flag_rapidocr_unreachable,
)


def test_flag_low_confidence_is_stable_string():
    """The string is part of the contract: don't drift it accidentally."""
    assert flag_low_confidence() == "low_confidence"
    assert flag_low_confidence() == flag_low_confidence()


def test_flag_rapidocr_fallback_is_stable_string():
    assert flag_rapidocr_fallback() == "rapidocr_fallback"


def test_flag_rapidocr_unreachable_is_stable_string():
    assert flag_rapidocr_unreachable() == "rapidocr_unreachable"


def test_flag_rapidocr_disabled_in_env_is_stable_string():
    assert flag_rapidocr_disabled_in_env() == "rapidocr_disabled_in_env"


def test_flag_docling_low_confidence_review_is_stable_string():
    assert flag_docling_low_confidence_review() == "docling_low_confidence_review"


def test_flag_missing_fields_with_two_fields():
    """Format: 'missing_fields:field1,field2'."""
    assert flag_missing_fields("cin", "cnss") == "missing_fields:cin,cnss"


def test_flag_missing_fields_with_one_field():
    """Single-field case is also valid (no trailing comma)."""
    assert flag_missing_fields("date_embauche") == "missing_fields:date_embauche"


def test_flag_missing_fields_with_three_fields():
    assert (
        flag_missing_fields("date_embauche", "salaire_brut", "cin")
        == "missing_fields:date_embauche,salaire_brut,cin"
    )


def test_canonical_flags_are_distinct():
    """Each canonical flag is a distinct string — no aliasing."""
    flags = {
        flag_low_confidence(),
        flag_rapidocr_fallback(),
        flag_rapidocr_unreachable(),
        flag_rapidocr_disabled_in_env(),
        flag_docling_low_confidence_review(),
    }
    assert len(flags) == 5