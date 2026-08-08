"""Tests for cohort key extraction."""

from __future__ import annotations

from app.anomalies.cohort import cohort_key
from app.ingestion.schemas import HRRecord


def _record(departement: str | None = None) -> HRRecord:
    return HRRecord(
        id="doc-1",
        revision=1,
        nom="Dupont",
        prenom="Jean",
        cin="AB123456",
        cnss="123456789",
        date_embauche="2020-01-15",
        salaire_brut=5000.0,
        poste="Dev",
        departement=departement,
    )


def test_cohort_key_with_departement():
    r = _record(departement="IT")
    assert cohort_key(r) == ("IT",)


def test_cohort_key_none_departement():
    r = _record(departement=None)
    assert cohort_key(r) is None


def test_cohort_key_empty_departement():
    r = _record(departement="")
    assert cohort_key(r) is None
