from __future__ import annotations

import logging
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised indirectly
    from docling.document_converter import DocumentConverter
except ImportError:  # pragma: no cover
    DocumentConverter = None  # type: ignore[assignment]

_REQUIRED_FIELDS = ("nom", "cin", "cnss", "date_embauche", "salaire_brut")


@dataclass(frozen=True)
class DoclingResult:
    markdown: str
    confidence: float


def run_docling(document_path: Path) -> DoclingResult:
    if DocumentConverter is None:  # pragma: no cover - dependency guard
        raise RuntimeError("docling is not installed")
    converter = DocumentConverter()
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

    field_values = {
        "nom": nom,
        "cin": cin,
        "cnss": cnss,
        "date_embauche": date_embauche,
        "salaire_brut": salaire_brut,
    }
    missing_fields = [
        name for name in _REQUIRED_FIELDS if field_values[name] is None
    ]

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

    if parsed.confidence < config.docling_confidence_threshold:
        record.flags.append(
            Flag(
                moteur="docling",
                detail="Confiance Docling sous le seuil",
                score=parsed.confidence,
            )
        )
    if missing_fields:
        record.flags.append(
            Flag(
                moteur="docling",
                detail="Champ(s) manquant(s) apres extraction Docling",
                score=parsed.confidence,
            )
        )

    return ExtractionResult(
        record=record,
        confidence=parsed.confidence,
        source="docling",
    )