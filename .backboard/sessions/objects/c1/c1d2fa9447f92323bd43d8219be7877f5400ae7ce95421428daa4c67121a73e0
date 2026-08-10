from __future__ import annotations

import pytest

from app.ingestion.parser_regex import (
    extract_cin,
    extract_cnss,
    extract_date_embauche,
    extract_nom_prenom,
    extract_salaire_brut,
)


def test_extract_cin_valid():
    assert extract_cin("CIN: AB123456") == "AB123456"


def test_extract_cin_invalid_returns_none():
    assert extract_cin("12345") is None


def test_extract_cnss_exact_9():
    assert extract_cnss("CNSS 123456789") == "123456789"


def test_extract_cnss_more_digits_truncates():
    assert extract_cnss("CNSS 1234567890123") == "123456789"


def test_extract_cnss_less_9_returns_none():
    assert extract_cnss("12345") is None


def test_extract_date_embauche_iso():
    assert extract_date_embauche("Date: 2021-05-01") == "2021-05-01"


def test_extract_date_embauche_slash_converted():
    # DD/MM/YYYY is the conventional Tunisian HR document format; the
    # parser reorders it into ISO 8601 (YYYY-MM-DD) for downstream use.
    assert extract_date_embauche("Embauche 01/06/2020") == "2020-06-01"


def test_extract_date_embauche_missing():
    assert extract_date_embauche("no date here") is None


def test_extract_salaire_brut_euros():
    assert extract_salaire_brut("Salaire brut : 2500 EUR") == pytest.approx(2500.0)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Salaire brut: 1 234,56", 1234.56),
        ("brut 3200,00", 3200.0),
    ],
)
def test_extract_salaire_brut_formats(text, expected):
    assert extract_salaire_brut(text) == pytest.approx(expected)


def test_extract_salaire_brut_missing():
    assert extract_salaire_brut("nom: Durand") is None


def test_extract_nom_prenom_two_tokens():
    nom, prenom = extract_nom_prenom("Jean Dupont")
    assert nom == "Jean"
    assert prenom == "Dupont"


def test_extract_nom_prenom_many_tokens():
    nom, prenom = extract_nom_prenom("Jean-Pierre Delacroix")
    assert nom == "Jean-Pierre"
    assert prenom == "Delacroix"


def test_extract_nom_prenom_empty():
    assert extract_nom_prenom("") == (None, None)
