from __future__ import annotations

import pytest

from app.ingestion.schemas import HRRecord, RecStatus


def test_hr_record_happy_path():
    rec = HRRecord(
        id="doc-1",
        nom="Dupont",
        prenom="Marie",
        cin="AB123456",
        cnss="123456789",
        date_embauche="2020-01-15",
        salaire_brut=3200.0,
        poste="RH",
        departement="Paris",
        confiance=0.95,
        statut=RecStatus.GREEN,
    )
    assert rec.cin == "AB123456"
    assert rec.cnss == "123456789"
    assert rec.statut == RecStatus.GREEN


def test_cin_format_validated():
    with pytest.raises(Exception):
        HRRecord(id="doc-2", cin="BAD")


def test_cnss_must_be_9_digits():
    with pytest.raises(Exception):
        HRRecord(id="doc-3", cnss="123")


def test_salaire_brut_must_be_positive():
    with pytest.raises(Exception):
        HRRecord(id="doc-4", salaire_brut=-1)


def test_record_missing_required_becomes_amber():
    rec = HRRecord(id="doc-5", nom="Dupont")
    assert rec.statut == RecStatus.RED
