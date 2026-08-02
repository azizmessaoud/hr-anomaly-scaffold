from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import httpx

from app.core.config import ExtractPipelineConfig
from app.ingestion.extraction_result import (
    ERR_VLM_INVALID_NUMERIC,
    ERR_VLM_MALFORMED_JSON,
    ERR_VLM_MISSING_REQUIRED_FIELD,
    ERR_VLM_NOT_OBJECT,
    ERR_VLM_UNREACHABLE,
    ExtractionResult,
    flag_vlm_fallback,
)
from app.ingestion.ollama_client import extract_hr_fields
from app.ingestion.schemas import Flag, HRRecord

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = ("nom", "cin", "cnss")

_EXTRACTION_PROMPT = (
    "Tu es un extracteur de documents RH. "
    "Retourne UNIQUEMENT un objet JSON valide, sans texte additionnel. "
    "Champs: nom, prenom, cin, cnss, date_embauche (YYYY-MM-DD), "
    "salaire_brut (nombre), poste, departement. "
    "Si un champ est absent, mets null."
)


def _pdf_to_image(pdf_path: Path) -> Path | None:
    """Render the first page of a PDF to a temp PNG image.

    Returns the path to the temp PNG on success, or None if the
    PDF cannot be rendered with the available tooling.

    Uses pypdfium2 (already in the dependency tree via docling) for
    PDF rasterisation — Pillow cannot open PDFs directly, and we are
    not permitted to install PyMuPDF / pdf2image / pdftoppm.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        if len(pdf) == 0:
            return None
        pil_img = pdf[0].render(scale=1).to_pil()
    except Exception:
        return None
    tmp = Path(tempfile.mkstemp(suffix=".png")[1])
    try:
        pil_img.save(tmp, format="PNG")
    except Exception:
        return None
    return tmp


def _parse_vlm_payload(payload: str) -> dict[str, object]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Reponse VLM non JSON: {payload[:200]}") from exc
    if not isinstance(data, dict):
        raise ValueError("Reponse VLM doit etre un objet JSON")
    return data


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().replace(",", ".")
        if not normalized:
            return None
        return float(normalized)
    raise ValueError(f"Valeur numerique invalide: {value!r}")


def _coerce_record(
    data: dict[str, object],
    *,
    doc_id: str,
    revision: int,
    config: ExtractPipelineConfig,
) -> tuple[HRRecord, list[str]]:
    flags: list[Flag] = []
    record = HRRecord(
        id=doc_id,
        revision=revision,
        nom=_optional_str(data.get("nom")),
        prenom=_optional_str(data.get("prenom")),
        cin=_optional_str(data.get("cin")),
        cnss=_optional_str(data.get("cnss")),
        date_embauche=_optional_str(data.get("date_embauche")),
        salaire_brut=_optional_float(data.get("salaire_brut")),
        poste=_optional_str(data.get("poste")),
        departement=_optional_str(data.get("departement")),
        confiance=config.vlm_default_confidence,
        flags=flags,
    )
    missing = [name for name in _REQUIRED_FIELDS if getattr(record, name) is None]
    if missing:
        flags.append(
            Flag(
                moteur="vlm",
                detail="Champ(s) manquant(s) apres extraction VLM",
                score=config.vlm_default_confidence,
            )
        )
    return record, missing


def _failure(*, source_msg: str, error_code: str) -> ExtractionResult:
    logger.warning("VLM extraction failed: %s", source_msg)
    return ExtractionResult(
        record=None,
        confidence=0.0,
        source="vlm",
        flags=(flag_vlm_fallback(),),
        erreur_traitement=error_code,
    )


def extract_with_vlm(
    document_path: Path,
    *,
    doc_id: str,
    revision: int = 0,
    config: ExtractPipelineConfig,
) -> ExtractionResult:
    image_path: str
    tmp_image: Path | None = None
    if document_path.suffix.lower() == ".pdf":
        converted = _pdf_to_image(document_path)
        if converted is None:
            return _failure(
                source_msg="PDF requires image conversion for VLM fallback; install PyMuPDF or pdf2image",
                error_code=ERR_VLM_MALFORMED_JSON,
            )
        tmp_image = converted
        image_path = str(tmp_image)
    else:
        image_path = str(document_path)
    try:
        raw = extract_hr_fields(image_path, _EXTRACTION_PROMPT, config)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return _failure(source_msg=str(exc), error_code=ERR_VLM_UNREACHABLE)
    except Exception as exc:
        return _failure(source_msg=str(exc), error_code=ERR_VLM_MALFORMED_JSON)
    finally:
        if tmp_image is not None and tmp_image.exists():
            tmp_image.unlink()

    try:
        data = _parse_vlm_payload(raw)
    except ValueError as exc:
        if "objet JSON" in str(exc):
            return _failure(source_msg=str(exc), error_code=ERR_VLM_NOT_OBJECT)
        return _failure(source_msg=str(exc), error_code=ERR_VLM_MALFORMED_JSON)

    try:
        record, missing = _coerce_record(data, doc_id=doc_id, revision=revision, config=config)
    except ValueError as exc:
        return _failure(source_msg=str(exc), error_code=ERR_VLM_INVALID_NUMERIC)

    if missing:
        return ExtractionResult(
            record=None,
            confidence=config.vlm_default_confidence,
            source="vlm",
            flags=(flag_vlm_fallback(),),
            erreur_traitement=f"{ERR_VLM_MISSING_REQUIRED_FIELD}:{','.join(missing)}",
        )

    return ExtractionResult(
        record=record,
        confidence=config.vlm_default_confidence,
        source="vlm",
        flags=(flag_vlm_fallback(),),
    )