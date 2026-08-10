from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.core.config import ExtractPipelineConfig
from app.ingestion.extraction_result import (
    ERR_RAPIDOCR_MISSING_REQUIRED_FIELD,
    ERR_RAPIDOCR_NO_TEXT,
    ERR_RAPIDOCR_UNREACHABLE,
    ExtractionResult,
    flag_rapidocr_fallback,
    flag_rapidocr_unreachable,
)
from app.ingestion.parser_regex import (
    extract_cin,
    extract_cnss,
    extract_date_embauche,
    extract_nom_prenom,
    extract_salaire_brut,
)
from app.ingestion.schemas import Flag, HRRecord
from app.pipeline.completeness import (
    RAPIDOCR_HARD_GATE_FIELDS,
    missing_required_fields,
)

logger = logging.getLogger(__name__)


def _pdf_to_numpy(pdf_path: Path) -> "np.ndarray | None":
    """Render the first page of a PDF to a numpy RGB array.

    Returns the numpy array on success, or None if the PDF
    cannot be rendered with the available tooling.

    Uses pypdfium2 (already in the dependency tree via docling) for
    PDF rasterisation.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        if len(pdf) == 0:
            return None
        pil_img = pdf[0].render(scale=1).to_pil()
        arr = np.array(pil_img.convert("RGB"))
    except Exception:
        return None
    return arr


def _coerce_record(
    text: str,
    *,
    doc_id: str,
    revision: int,
    config: ExtractPipelineConfig,
) -> tuple[HRRecord, list[str]]:
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
        confiance=config.rapidocr_default_confidence,
    )
    hard_missing = missing_required_fields(record, RAPIDOCR_HARD_GATE_FIELDS)
    shared_missing = missing_required_fields(record)
    if shared_missing:
        record.flags.append(
            Flag(
                moteur="rapidocr",
                detail=f"Champ(s) manquant(s) apres extraction RapidOCR: {', '.join(shared_missing)}",
                score=config.rapidocr_default_confidence,
            )
        )
    return record, hard_missing


def _failure(*, source_msg: str, error_code: str) -> ExtractionResult:
    logger.warning("RapidOCR extraction failed: %s", source_msg)
    return ExtractionResult(
        record=None,
        confidence=0.0,
        source="rapidocr",
        flags=(flag_rapidocr_fallback(),),
        erreur_traitement=error_code,
    )


def extract_with_rapidocr(
    document_path: Path,
    *,
    doc_id: str,
    revision: int = 0,
    config: ExtractPipelineConfig,
) -> ExtractionResult:
    if not config.rapidocr_enabled:
        return ExtractionResult(
            record=None,
            confidence=0.0,
            source="rapidocr",
            flags=(flag_rapidocr_unreachable(),),
            erreur_traitement=ERR_RAPIDOCR_UNREACHABLE,
        )

    image_array: "np.ndarray | None" = None
    tmp_image: Path | None = None

    if document_path.suffix.lower() == ".pdf":
        arr = _pdf_to_numpy(document_path)
        if arr is None:
            return _failure(
                source_msg="PDF requires rasterization for RapidOCR; install pypdfium2",
                error_code=ERR_RAPIDOCR_UNREACHABLE,
            )
        image_array = arr
    else:
        try:
            import numpy as np
            from PIL import Image
        except ImportError:
            return _failure(
                source_msg="RapidOCR requires numpy and Pillow for non-PDF input",
                error_code=ERR_RAPIDOCR_UNREACHABLE,
            )
        try:
            img = Image.open(document_path)
            image_array = np.array(img.convert("RGB"))
        except Exception as exc:
            return _failure(
                source_msg=f"Failed to open image for RapidOCR: {exc}",
                error_code=ERR_RAPIDOCR_UNREACHABLE,
            )

    if image_array is None:
        return _failure(
            source_msg="RapidOCR could not render input to an image array",
            error_code=ERR_RAPIDOCR_UNREACHABLE,
        )

    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        return _failure(
            source_msg=f"RapidOCR engine not importable: {exc}",
            error_code=ERR_RAPIDOCR_UNREACHABLE,
        )

    try:
        engine = RapidOCR()
        result = engine(image_array)
    except Exception as exc:
        logger.warning("RapidOCR engine error: %s", exc)
        return ExtractionResult(
            record=None,
            confidence=0.0,
            source="rapidocr",
            flags=(flag_rapidocr_unreachable(), flag_rapidocr_fallback()),
            erreur_traitement=ERR_RAPIDOCR_UNREACHABLE,
        )

    if result[0] is None:
        return _failure(
            source_msg="RapidOCR produced no text from the document",
            error_code=ERR_RAPIDOCR_NO_TEXT,
        )

    det_lines = result[0]
    confidences = [line[2] for line in det_lines if isinstance(line[2], (int, float))]
    doc_confidence = (
        sum(confidences) / len(confidences) if confidences else 0.0
    )

    full_text = " ".join(line[1] for line in det_lines if isinstance(line[1], str))
    logger.debug("RapidOCR raw detected text (%d lines): %s", len(det_lines), full_text[:800])

    try:
        record, missing = _coerce_record(
            full_text, doc_id=doc_id, revision=revision, config=config
        )
    except ValueError as exc:
        return _failure(source_msg=str(exc), error_code=ERR_RAPIDOCR_MISSING_REQUIRED_FIELD)

    if missing:
        return ExtractionResult(
            record=None,
            confidence=doc_confidence,
            source="rapidocr",
            flags=(flag_rapidocr_fallback(),),
            erreur_traitement=f"{ERR_RAPIDOCR_MISSING_REQUIRED_FIELD}:{','.join(missing)}",
        )

    return ExtractionResult(
        record=record,
        confidence=doc_confidence,
        source="rapidocr",
        flags=(flag_rapidocr_fallback(),),
    )