from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import ExtractPipelineConfig
from app.ingestion.extraction_result import ExtractionResult
from app.ingestion.parser_regex import (
    extract_cin,
    extract_cnss,
    extract_date_embauche,
    extract_nom_prenom,
    extract_salaire_brut,
)
from app.ingestion.schemas import Flag, HRRecord
from app.pipeline.completeness import missing_required_fields

logger = logging.getLogger(__name__)

# Keep Docling out of the application import path.  Its import is heavyweight
# and may initialize model resources; load it only when extraction is needed.
DocumentConverter = None

@dataclass(frozen=True)
class DoclingResult:
    markdown: str
    confidence: float


def _extract_embedded_pdf_text(document_path: Path) -> str | None:
    """Read a PDF text layer without starting Docling's layout models.

    Most payroll PDFs are digitally generated and already contain selectable
    text.  Running Docling's full layout/OCR pipeline for those files is
    unnecessary and can take several minutes on a WSL CPU.  Scanned PDFs
    return no useful text here and continue through the normal Docling path.
    """
    if document_path.suffix.lower() != ".pdf":
        return None
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(document_path))
        text = "\n".join(
            pdf[index].get_textpage().get_text_range()
            for index in range(len(pdf))
        ).strip()
    except Exception:
        return None
    return text if len(text) >= 20 else None


@lru_cache(maxsize=1)
def _docling_converter(converter_type: object) -> object:
    """Reuse the heavyweight Docling converter within a worker process."""
    return converter_type()


def _get_docling_converter() -> object:
    global DocumentConverter
    if DocumentConverter is None:  # pragma: no cover - dependency guard
        try:
            from docling.document_converter import DocumentConverter as converter_type
        except ImportError as exc:
            raise RuntimeError("docling is not installed") from exc
        DocumentConverter = converter_type
    return _docling_converter(DocumentConverter)


def run_docling(document_path: Path) -> DoclingResult:
    embedded_text = _extract_embedded_pdf_text(document_path)
    if embedded_text is not None:
        return DoclingResult(markdown=embedded_text, confidence=0.9)

    converter = _get_docling_converter()
    result = converter.convert(document_path)
    md = result.document.export_to_markdown()
    raw_conf = getattr(result, "confidence", 0.9)
    if isinstance(raw_conf, (int, float)):
        confidence = float(raw_conf)
    else:
        confidence = float(getattr(raw_conf, "value", 0.9))
    return DoclingResult(markdown=md, confidence=confidence)


def extract_from_docling(
    document_path: Path,
    *,
    doc_id: str,
    revision: int = 0,
    config: ExtractPipelineConfig,
) -> ExtractionResult:
    parsed = run_docling(document_path)
    text = parsed.markdown
    nom, prenom = extract_nom_prenom(text)
    cin = extract_cin(text)
    cnss = extract_cnss(text)
    date_embauche = extract_date_embauche(text)
    salaire_brut = extract_salaire_brut(text)

    record = HRRecord(
        id=doc_id,
        revision=revision,
        nom=nom,
        prenom=prenom,
        cin=cin,
        cnss=cnss,
        date_embauche=date_embauche,
        salaire_brut=salaire_brut,
        confiance=parsed.confidence,
    )
    missing_fields = missing_required_fields(record)

    if parsed.confidence < config.docling_confidence_threshold:
        record.flags.append(
            Flag(
                moteur="docling",
                detail="Confiance Docling sous le seuil",
                score=parsed.confidence,
            )
        )
    if missing_fields:
        detail = f"Champ(s) manquant(s) apres extraction Docling: {', '.join(missing_fields)}"
        record.flags.append(
            Flag(
                moteur="docling",
                detail=detail,
                score=parsed.confidence,
            )
        )

    return ExtractionResult(
        record=record,
        confidence=parsed.confidence,
        source="docling",
    )