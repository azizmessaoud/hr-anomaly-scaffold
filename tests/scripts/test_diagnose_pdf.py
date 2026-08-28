from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.diagnose_pdf import diagnose


def test_diagnose_passes_one_surrogate_id_to_docling(tmp_path: Path):
    pdf = tmp_path / "document.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    extraction = MagicMock(
        succeeded=True,
        erreur_traitement=None,
        confidence=0.9,
        flags=(),
        record=None,
    )

    with patch(
        "app.ingestion.docling_path.extract_from_docling",
        return_value=extraction,
    ) as extract:
        result = diagnose(pdf, engine="docling")

    extract.assert_called_once()
    assert extract.call_args.kwargs["doc_id"]
    assert result["docling"]["succeeded"] is True
