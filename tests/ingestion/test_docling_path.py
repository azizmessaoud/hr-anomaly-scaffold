from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import ExtractPipelineConfig
from app.ingestion.docling_path import extract_from_docling


@pytest.fixture
def fake_document(tmp_path: Path) -> Path:
    pdf = tmp_path / "upload_123.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return pdf


@pytest.fixture
def test_config() -> ExtractPipelineConfig:
    return ExtractPipelineConfig(
        docling_confidence_threshold=0.75,
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5vl:7b",
        ollama_timeout_seconds=120,
        vlm_default_confidence=0.5,
    )


def _docling_mock(markdown: str, confidence: float) -> MagicMock:
    fake_result = MagicMock()
    fake_result.document.export_to_markdown.return_value = markdown
    fake_result.confidence = confidence
    return fake_result


def test_extract_from_docling_happy_path(fake_document: Path, test_config: ExtractPipelineConfig):
    with patch("app.ingestion.docling_path.DocumentConverter") as MockConverter:
        MockConverter.return_value.convert.return_value = _docling_mock(
            "Dupont Marie\n"
            "CIN: AB123456\nCNSS: 123456789\n"
            "Date d'embauche: 2020-01-15\n"
            "Salaire brut : 3200",
            0.92,
        )
        result = extract_from_docling(fake_document, doc_id="doc-x", config=test_config)

    assert result.source == "docling"
    assert result.succeeded is True
    assert result.record is not None
    assert result.record.nom == "Dupont"
    assert result.record.prenom == "Marie"
    assert result.record.cin == "AB123456"
    assert result.record.confiance == pytest.approx(0.92)


def test_extract_from_docling_low_confidence_flags_amber(fake_document: Path, test_config: ExtractPipelineConfig):
    """A low-confidence Docling result surfaces concerns through flags rather
    than assigning a status directly — the orchestrator assesses quality."""
    with patch("app.ingestion.docling_path.DocumentConverter") as MockConverter:
        MockConverter.return_value.convert.return_value = _docling_mock(
            "Nom: Dupont\nPrenom: Marie\n",
            0.45,
        )
        result = extract_from_docling(fake_document, doc_id="doc-x", config=test_config)

    assert result.succeeded is True
    assert result.record is not None
    assert result.confidence == pytest.approx(0.45)
    assert any(flag.moteur == "docling" for flag in result.record.flags)


def test_extract_from_docling_raises_on_docling_failure(fake_document: Path, test_config: ExtractPipelineConfig):
    """Docling failure surfaces as a raised exception; caller decides fallback."""
    with patch("app.ingestion.docling_path.DocumentConverter") as MockConverter:
        MockConverter.return_value.convert.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            extract_from_docling(fake_document, doc_id="doc-x", config=test_config)


def test_extract_from_docling_missing_required_field_is_amber(fake_document: Path, test_config: ExtractPipelineConfig):
    with patch("app.ingestion.docling_path.DocumentConverter") as MockConverter:
        MockConverter.return_value.convert.return_value = _docling_mock(
            "Nom: Dupont\nPrenom: Marie\n",  # no CIN, CNSS, date, salaire
            0.95,
        )
        result = extract_from_docling(fake_document, doc_id="doc-x", config=test_config)

    assert result.succeeded is True
    assert result.record is not None
    assert any("manquant" in flag.detail for flag in result.record.flags)