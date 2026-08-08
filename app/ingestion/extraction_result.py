from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.ingestion.schemas import HRRecord

ExtractionSource = Literal["docling", "rapidocr"]


@dataclass(frozen=True)
class ExtractionResult:
    """Stable boundary contract for Docling and RapidOCR extraction paths.

    The task/orchestration layer consumes this object and never sees raw dicts,
    raw exceptions, or unstructured status strings. When an extractor fails
    (missing file, OCR engine unavailable, missing required fields, …) it returns
    this object with ``record=None`` and a populated ``erreur_traitement``.
    """

    record: HRRecord | None
    confidence: float
    source: ExtractionSource
    flags: tuple[str, ...] = ()
    erreur_traitement: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.record is not None and self.erreur_traitement is None


# Centralised reason strings — referenced by both extractors and the task layer
# so a typo in one place can't drift the contract.
ERR_RAPIDOCR_NO_TEXT = "rapidocr_no_text"
ERR_RAPIDOCR_MISSING_REQUIRED_FIELD = "rapidocr_missing_required_field"
ERR_RAPIDOCR_UNREACHABLE = "rapidocr_unreachable"
ERR_FILE_MISSING = "file_missing"
ERR_DOCLING_FAILED = "docling_failed"
ERR_DOCLING_PARSE_FAILED = "docling_parse_failed"


def flag_low_confidence() -> str:
    return "low_confidence"


def flag_rapidocr_fallback() -> str:
    """RapidOCR rescue path was used successfully."""
    return "rapidocr_fallback"


def flag_rapidocr_unreachable() -> str:
    """RapidOCR expected but transport failed (engine not available).

    Reviewer should investigate whether the onnxruntime model files are present
    and the engine is importable. Distinct from ``rapidocr_disabled_in_env``
    (intentional config choice).
    """
    return "rapidocr_unreachable"


def flag_rapidocr_disabled_in_env() -> str:
    """RapidOCR intentionally disabled by config (``RAPIDOCR_ENABLED=false``).

    Reviewer should accept the Docling result and focus on completeness;
    this is a deliberate design choice, not an operational problem.
    """
    return "rapidocr_disabled_in_env"


def flag_docling_low_confidence_review() -> str:
    """Docling produced a usable record below the confidence threshold.

    Reviewer should inspect and decide: the record exists but the read
    is shaky. Does NOT apply when Docling succeeded at full confidence.
    """
    return "docling_low_confidence_review"


def flag_missing_fields(*fields: str) -> str:
    """Reviewer-visible flag listing required fields that are absent
    after extraction. Format: ``missing_fields:field1,field2``.

    Multiple instances may be combined by callers (one per source); the
    ``flags_from_strings`` projector turns each into a ``Flag`` row.
    """
    return f"missing_fields:{','.join(fields)}"