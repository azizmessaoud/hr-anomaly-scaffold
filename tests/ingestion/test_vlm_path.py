from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.core.config import ExtractPipelineConfig
from app.ingestion.extraction_result import (
    ERR_VLM_INVALID_NUMERIC,
    ERR_VLM_MALFORMED_JSON,
    ERR_VLM_MISSING_REQUIRED_FIELD,
    ERR_VLM_NOT_OBJECT,
    ERR_VLM_UNREACHABLE,
)
from app.ingestion.vlm_path import extract_with_vlm


@pytest.fixture
def fake_image(tmp_path: Path) -> Path:
    img = tmp_path / "scan.png"
    img.write_bytes(b"PNGDATA")
    return img


@pytest.fixture
def test_config() -> ExtractPipelineConfig:
    return ExtractPipelineConfig(
        docling_confidence_threshold=0.75,
        vlm_enabled=True,
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5vl:7b",
        ollama_timeout_seconds=120,
        vlm_default_confidence=0.5,
    )


def test_extract_with_vlm_happy_path(fake_image: Path, test_config: ExtractPipelineConfig):
    mock_json = (
        '{"nom": "Durand", "prenom": "Pierre", "cin": "CD789012", '
        '"cnss": "987654321", "date_embauche": "2019-07-01", '
        '"salaire_brut": 4100, "poste": "Manager", "departement": "Lyon"}'
    )

    with patch(
        "app.ingestion.vlm_path.extract_hr_fields", return_value=mock_json
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.source == "vlm"
    assert result.succeeded is True
    assert result.record is not None
    assert result.record.nom == "Durand"
    assert result.record.prenom == "Pierre"
    assert result.record.confiance == pytest.approx(0.5)
    assert "vlm_fallback" in result.flags


def test_extract_with_vlm_malformed_json_returns_red(fake_image: Path, test_config: ExtractPipelineConfig):
    """Malformed JSON must map to a typed failure (RED), never raise.

    Required by the architecture: error modes are part of the boundary
    contract and ``erreur_traitement`` is populated consistently.
    """
    with patch("app.ingestion.vlm_path.extract_hr_fields", return_value="NOT JSON"):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is False
    assert result.record is None
    assert result.erreur_traitement == ERR_VLM_MALFORMED_JSON
    assert "vlm_fallback" in result.flags


def test_extract_with_vlm_non_object_json_returns_red(fake_image: Path, test_config: ExtractPipelineConfig):
    with patch(
        "app.ingestion.vlm_path.extract_hr_fields",
        return_value="[1, 2, 3]",
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is False
    assert result.erreur_traitement == ERR_VLM_NOT_OBJECT


def test_extract_with_vlm_missing_required_fields_returns_red(fake_image: Path, test_config: ExtractPipelineConfig):
    """Missing required fields fail the boundary contract — RED with the
    names of the missing fields in ``erreur_traitement``.
    """
    mock_json = '{"nom": "Durand", "prenom": "Pierre"}'  # no cin, cnss

    with patch(
        "app.ingestion.vlm_path.extract_hr_fields", return_value=mock_json
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is False
    assert result.record is None
    assert result.erreur_traitement is not None
    assert result.erreur_traitement.startswith(ERR_VLM_MISSING_REQUIRED_FIELD)
    assert "cin,cnss" in result.erreur_traitement


def test_extract_with_vlm_shared_completeness_adds_missing_fields_flag(fake_image: Path, test_config: ExtractPipelineConfig):
    """Hard gate passes (nom/cin/cnss), but shared payroll completeness is still missing fields."""
    mock_json = (
        '{"nom": "Durand", "prenom": "Pierre", "cin": "CD789012", '
        '"cnss": "987654321", "date_embauche": null, '
        '"salaire_brut": null, "poste": "Manager", "departement": "Lyon"}'
    )

    with patch(
        "app.ingestion.vlm_path.extract_hr_fields", return_value=mock_json
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is True
    assert result.record is not None
    missing_flag = next(
        (flag for flag in result.record.flags if "manquant" in flag.detail),
        None,
    )
    assert missing_flag is not None
    listed = {f.strip() for f in missing_flag.detail.split(":")[-1].split(",")}
    assert listed == {"date_embauche", "salaire_brut"}


def test_extract_with_vlm_ollama_client_failure_returns_red(fake_image: Path, test_config: ExtractPipelineConfig):
    """If the Ollama client raises (HTTP / network), the boundary
    contract turns that into a typed failure too.
    """
    with patch(
        "app.ingestion.vlm_path.extract_hr_fields",
        side_effect=RuntimeError("ollama down"),
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is False
    assert result.record is None
    assert result.erreur_traitement == ERR_VLM_MALFORMED_JSON


def test_extract_with_vlm_transport_failure_returns_unreachable(fake_image: Path, test_config: ExtractPipelineConfig):
    with patch(
        "app.ingestion.vlm_path.extract_hr_fields",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is False
    assert result.record is None
    assert result.erreur_traitement == ERR_VLM_UNREACHABLE
    # Canonical flag: vlm_unreachable signals a transport-level problem.
    assert "vlm_unreachable" in result.flags


def test_extract_with_vlm_invalid_numeric_returns_red(fake_image: Path, test_config: ExtractPipelineConfig):
    mock_json = (
        '{"nom": "Durand", "cin": "AB123456", "cnss": "123456789", '
        '"salaire_brut": "not-a-number"}'
    )
    with patch(
        "app.ingestion.vlm_path.extract_hr_fields", return_value=mock_json
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is False
    assert result.erreur_traitement == ERR_VLM_INVALID_NUMERIC


def test_extract_with_vlm_timeout_returns_unreachable(fake_image: Path, test_config: ExtractPipelineConfig):
    """Timeout exception is also a transport-level problem: vlm_unreachable flag."""
    with patch(
        "app.ingestion.vlm_path.extract_hr_fields",
        side_effect=httpx.TimeoutException("timeout"),
    ):
        result = extract_with_vlm(fake_image, doc_id="doc-x", config=test_config)

    assert result.succeeded is False
    assert result.record is None
    assert result.erreur_traitement == ERR_VLM_UNREACHABLE
    assert "vlm_unreachable" in result.flags