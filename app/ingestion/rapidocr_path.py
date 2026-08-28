from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from functools import lru_cache

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

@lru_cache(maxsize=1)
def _rapidocr_engine(factory: object | None = None, model_path: str | None = None) -> object:
    """Create RapidOCR once per worker process instead of per upload."""
    if factory is None:
        from rapidocr_onnxruntime import RapidOCR

        factory = RapidOCR
    # The packaged RapidOCR models are the safe default.  The project setting
    # is an override, but the scaffold's default path may not exist in a
    # fresh checkout where the package models are installed.
    kwargs = {"rec_model_path": model_path} if model_path and Path(model_path).is_file() else {}
    return factory(**kwargs)


def _pdf_to_numpy(pdf_path: Path) -> "list[np.ndarray] | None":
    """Render every page of a PDF to numpy RGB arrays.

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
        arrays = [
            np.array(pdf[index].render(scale=1).to_pil().convert("RGB"))
            for index in range(len(pdf))
        ]
    except Exception:
        return None
    return arrays or None


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
    if document_path.suffix.lower() == ".pdf":
        rendered = _pdf_to_numpy(document_path)
        if rendered is None:
            return _failure(
                source_msg="PDF requires rasterization for RapidOCR; install pypdfium2",
                error_code=ERR_RAPIDOCR_UNREACHABLE,
            )
        image_array = rendered
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

        engine = _rapidocr_engine(RapidOCR, config.rapidocr_model_path)
    except (ImportError, OSError, ValueError) as exc:
        return _failure(
            source_msg=f"RapidOCR engine not importable: {exc}",
            error_code=ERR_RAPIDOCR_UNREACHABLE,
        )

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_ocr_pages, engine, image_array)
    try:
        result = future.result(timeout=config.rapidocr_timeout_seconds)
    except TimeoutError:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        return _failure(
            source_msg="RapidOCR timed out",
            error_code=ERR_RAPIDOCR_UNREACHABLE,
        )
    except Exception as exc:
        executor.shutdown(wait=False, cancel_futures=True)
        logger.warning("RapidOCR engine error: %s", exc)
        return ExtractionResult(
            record=None,
            confidence=0.0,
            source="rapidocr",
            flags=(flag_rapidocr_unreachable(), flag_rapidocr_fallback()),
            erreur_traitement=ERR_RAPIDOCR_UNREACHABLE,
        )
    else:
        executor.shutdown(wait=True)

    if result[0] is None:
        return _failure(
            source_msg="RapidOCR produced no text from the document",
            error_code=ERR_RAPIDOCR_NO_TEXT,
        )

    det_lines = result[0]
    confidences: list[float] = []
    for line in det_lines:
        try:
            confidences.append(float(line[2]))
        except (IndexError, TypeError, ValueError):
            continue
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


def _ocr_pages(engine: object, images: "list[object] | object") -> tuple[list[list[object]] | None, object]:
    pages = images if isinstance(images, list) else [images]
    all_lines: list[list[object]] = []
    elapsed: list[object] = []
    for image in pages:
        page_result = engine(image)
        if not page_result or page_result[0] is None:
            continue
        all_lines.extend(page_result[0])
        if len(page_result) > 1:
            elapsed.append(page_result[1])
    return (all_lines or None, elapsed)
