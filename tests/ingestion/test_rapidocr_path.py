"""Tests for the RapidOCR extraction path.

The module handles PDF rasterization, OCR engine lifecycle, and record
coercion. Tests mock the RapidOCR engine and _pdf_to_numpy to isolate
the logic from external dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import ExtractPipelineConfig
from app.ingestion.extraction_result import (
    ERR_RAPIDOCR_MISSING_REQUIRED_FIELD,
    ERR_RAPIDOCR_NO_TEXT,
    ERR_RAPIDOCR_UNREACHABLE,
)
from app.ingestion.rapidocr_path import extract_with_rapidocr


@pytest.fixture
def test_config() -> ExtractPipelineConfig:
    return ExtractPipelineConfig(
        docling_confidence_threshold=0.75,
        rapidocr_enabled=True,
        rapidocr_model_path="models/rapidocr/en_ppocr_server_v2.0_infer.onnx",
        rapidocr_timeout_seconds=30,
        rapidocr_default_confidence=0.6,
    )


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    """Create a minimal PDF-like file for testing."""
    pdf = tmp_path / "scan.pdf"
    # Minimal PDF header — just enough to pass suffix check
    pdf.write_bytes(b"%PDF-1.4 test content")
    return pdf


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_extract_with_rapidocr_happy_path(fake_pdf: Path, test_config: ExtractPipelineConfig):
    """OCR finds text, all fields extracted, record returned."""
    mock_result = [
        [
            ([10, 10, 100, 50], "Nom: Dupont Pierre", 0.95),
            ([10, 60, 100, 100], "CIN: AB123456", 0.90),
            ([10, 110, 100, 150], "CNSS: 123456789", 0.88),
            ([10, 160, 100, 200], "Date embauche: 2020-01-15", 0.92),
            ([10, 210, 100, 250], "Salaire: 5000", 0.87),
            ([10, 260, 100, 300], "Departement: IT", 0.91),
        ]
    ]

    with patch("app.ingestion.rapidocr_path._pdf_to_numpy") as mock_raster:
        mock_raster.return_value = MagicMock()  # numpy array mock
        with patch("rapidocr_onnxruntime.RapidOCR") as MockOCR:
            MockOCR.return_value.return_value = mock_result
            result = extract_with_rapidocr(
                fake_pdf, doc_id="doc-x", revision=0, config=test_config
            )

    assert result.succeeded is True
    assert result.record is not None
    assert result.source == "rapidocr"
    assert "rapidocr_fallback" in result.flags


# ---------------------------------------------------------------------------
# No text detected
# ---------------------------------------------------------------------------


def test_extract_no_text_returns_no_text_error(fake_pdf: Path, test_config: ExtractPipelineConfig):
    """OCR engine returns None — no text on page."""
    with patch("app.ingestion.rapidocr_path._pdf_to_numpy") as mock_raster:
        mock_raster.return_value = MagicMock()
        with patch("rapidocr_onnxruntime.RapidOCR") as MockOCR:
            MockOCR.return_value.return_value = (None,)
            result = extract_with_rapidocr(
                fake_pdf, doc_id="doc-x", revision=0, config=test_config
            )

    assert result.succeeded is False
    assert result.record is None
    assert result.erreur_traitement == ERR_RAPIDOCR_NO_TEXT


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


def test_extract_missing_required_fields(fake_pdf: Path, test_config: ExtractPipelineConfig):
    """OCR finds text but missing hard-gate fields (nom/cin/cnss)."""
    mock_result = [
        [
            ([10, 10, 100, 50], "Salaire: 5000", 0.90),
        ]
    ]

    with patch("app.ingestion.rapidocr_path._pdf_to_numpy") as mock_raster:
        mock_raster.return_value = MagicMock()
        with patch("rapidocr_onnxruntime.RapidOCR") as MockOCR:
            MockOCR.return_value.return_value = mock_result
            result = extract_with_rapidocr(
                fake_pdf, doc_id="doc-x", revision=0, config=test_config
            )

    assert result.succeeded is False
    assert result.record is None
    assert ERR_RAPIDOCR_MISSING_REQUIRED_FIELD in result.erreur_traitement


# ---------------------------------------------------------------------------
# Engine exception → unreachable
# ---------------------------------------------------------------------------


def test_extract_engine_exception_returns_unreachable(fake_pdf: Path, test_config: ExtractPipelineConfig):
    """RapidOCR engine throws — treated as unreachability."""
    with patch("app.ingestion.rapidocr_path._pdf_to_numpy") as mock_raster:
        mock_raster.return_value = MagicMock()
        with patch("rapidocr_onnxruntime.RapidOCR") as MockOCR:
            MockOCR.return_value.side_effect = RuntimeError("engine crashed")
            result = extract_with_rapidocr(
                fake_pdf, doc_id="doc-x", revision=0, config=test_config
            )

    assert result.succeeded is False
    assert result.record is None
    assert result.erreur_traitement == ERR_RAPIDOCR_UNREACHABLE
    assert "rapidocr_unreachable" in result.flags


# ---------------------------------------------------------------------------
# PDF rasterization failure
# ---------------------------------------------------------------------------


def test_extract_pdf_rasterization_failure(fake_pdf: Path, test_config: ExtractPipelineConfig):
    """PDF cannot be rasterized — treated as unreachability."""
    with patch("app.ingestion.rapidocr_path._pdf_to_numpy") as mock_raster:
        mock_raster.return_value = None
        result = extract_with_rapidocr(
            fake_pdf, doc_id="doc-x", revision=0, config=test_config
        )

    assert result.succeeded is False
    assert result.erreur_traitement == ERR_RAPIDOCR_UNREACHABLE


# ---------------------------------------------------------------------------
# Disabled config
# ---------------------------------------------------------------------------


def test_extract_disabled_returns_unreachable(fake_pdf: Path):
    """When rapidocr_enabled=False, returns unreachable."""
    config = ExtractPipelineConfig(
        docling_confidence_threshold=0.75,
        rapidocr_enabled=False,
        rapidocr_model_path="models/rapidocr/en_ppocr_server_v2.0_infer.onnx",
        rapidocr_timeout_seconds=30,
        rapidocr_default_confidence=0.6,
    )
    result = extract_with_rapidocr(
        fake_pdf, doc_id="doc-x", revision=0, config=config
    )

    assert result.succeeded is False
    assert result.erreur_traitement == ERR_RAPIDOCR_UNREACHABLE
