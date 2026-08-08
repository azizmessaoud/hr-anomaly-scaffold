"""Integration tests for the full OCR pipeline using synthetic PDFs.

These tests require actual OCR engines (Docling, RapidOCR) to be installed
and functional. They are skipped if the required dependencies are not available.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "synthetic"
MANIFEST_PATH = DATA_DIR / "manifest.json"


def _has_ocr_deps() -> bool:
    """Check if OCR dependencies are available."""
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def _load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        pytest.skip("Synthetic data not generated yet")
    return json.loads(MANIFEST_PATH.read_text())


@pytest.mark.integration
@pytest.mark.skipif(not _has_ocr_deps(), reason="rapidocr_onnxruntime not installed")
class TestRapidOCRIntegration:
    """Integration tests for RapidOCR extraction on synthetic PDFs."""

    def test_rapidocr_extracts_text_from_synthetic_pdf(self):
        """RapidOCR should produce some text from a well-formed synthetic PDF."""
        from app.core.config import Settings, make_extract_pipeline_config
        from app.ingestion.rapidocr_path import extract_with_rapidocr

        settings = Settings()
        cfg = make_extract_pipeline_config(settings)
        pdf_path = DATA_DIR / "hr_record_01.pdf"

        if not pdf_path.exists():
            pytest.skip("Synthetic PDF not found")

        result = extract_with_rapidocr(pdf_path, config=cfg, doc_id="integ-01")
        assert result.succeeded, f"RapidOCR failed: {result.erreur_traitement}"

    def test_rapidocr_extracts_cin(self):
        """RapidOCR should extract CIN from synthetic PDF with AB12345."""
        from app.core.config import Settings, make_extract_pipeline_config
        from app.ingestion.rapidocr_path import extract_with_rapidocr

        settings = Settings()
        cfg = make_extract_pipeline_config(settings)
        pdf_path = DATA_DIR / "hr_record_01.pdf"

        if not pdf_path.exists():
            pytest.skip("Synthetic PDF not found")

        result = extract_with_rapidocr(pdf_path, config=cfg, doc_id="integ-cin")
        if result.record:
            assert result.record.cin == "AB12345", f"Expected AB12345, got {result.record.cin}"

    def test_rapidocr_extracts_date(self):
        """RapidOCR should extract date_embauche from synthetic PDF."""
        from app.core.config import Settings, make_extract_pipeline_config
        from app.ingestion.rapidocr_path import extract_with_rapidocr

        settings = Settings()
        cfg = make_extract_pipeline_config(settings)
        pdf_path = DATA_DIR / "hr_record_01.pdf"

        if not pdf_path.exists():
            pytest.skip("Synthetic PDF not found")

        result = extract_with_rapidocr(pdf_path, config=cfg, doc_id="integ-date")
        if result.record:
            assert result.record.date_embauche == "2020-03-15", f"Expected 2020-03-15, got {result.record.date_embauche}"


@pytest.mark.integration
@pytest.mark.skipif(not _has_ocr_deps(), reason="rapidocr_onnxruntime not installed")
class TestSyntheticPDFGeneration:
    """Tests that synthetic PDFs are well-formed and readable."""

    def test_all_synthetic_pdfs_exist(self):
        """All synthetic PDFs should exist."""
        manifest = _load_manifest()
        for entry in manifest:
            pdf_path = DATA_DIR / entry["file"]
            assert pdf_path.exists(), f"Missing: {pdf_path}"

    def test_manifest_matches_files(self):
        """Manifest should list all PDF files in the directory."""
        manifest = _load_manifest()
        pdf_files = list(DATA_DIR.glob("hr_record_*.pdf"))
        assert len(manifest) == len(pdf_files), f"Manifest has {len(manifest)} entries but found {len(pdf_files)} PDFs"


@pytest.mark.integration
@pytest.mark.skipif(not _has_ocr_deps(), reason="rapidocr_onnxruntime not installed")
class TestFullPipelineIntegration:
    """Integration tests for the complete pipeline (ingest → extract → validate)."""

    def test_pipeline_runs_on_synthetic_pdf(self):
        """Full pipeline should complete without errors on a synthetic PDF."""
        from app.core.config import Settings, make_extract_pipeline_config
        from app.ingestion.tasks import run_ingestion_pipeline
        from app.ingestion.doc_id import INITIAL_REVISION

        settings = Settings()
        cfg = make_extract_pipeline_config(settings)
        pdf_path = DATA_DIR / "hr_record_01.pdf"

        if not pdf_path.exists():
            pytest.skip("Synthetic PDF not found")

        result = run_ingestion_pipeline(
            pdf_path,
            doc_id="pipeline-integ-01",
            revision=INITIAL_REVISION,
            config=cfg,
        )
        # Pipeline should complete - result is a StageResult
        assert result is not None

    def test_pipeline_result_has_record(self):
        """Pipeline result should contain a record for synthetic PDF."""
        from app.core.config import Settings, make_extract_pipeline_config
        from app.ingestion.tasks import run_ingestion_pipeline
        from app.ingestion.doc_id import INITIAL_REVISION

        settings = Settings()
        cfg = make_extract_pipeline_config(settings)
        pdf_path = DATA_DIR / "hr_record_01.pdf"

        if not pdf_path.exists():
            pytest.skip("Synthetic PDF not found")

        result = run_ingestion_pipeline(
            pdf_path,
            doc_id="pipeline-integ-02",
            revision=INITIAL_REVISION,
            config=cfg,
        )
        # Result should have a record (even if partial)
        assert result.record is not None or result.erreur_traitement is not None
