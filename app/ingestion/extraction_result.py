from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.ingestion.schemas import HRRecord

ExtractionSource = Literal["docling", "vlm"]


@dataclass(frozen=True)
class ExtractionResult:
    """Stable boundary contract for Docling and VLM extraction paths.

    The task/orchestration layer consumes this object and never sees raw dicts,
    raw exceptions, or unstructured status strings. When an extractor fails
    (missing file, malformed VLM JSON, missing required fields, …) it returns
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
ERR_VLM_MALFORMED_JSON = "vlm_malformed_json"
ERR_VLM_NOT_OBJECT = "vlm_response_not_object"
ERR_VLM_MISSING_REQUIRED_FIELD = "vlm_missing_required_field"
ERR_VLM_INVALID_NUMERIC = "vlm_invalid_numeric"
ERR_VLM_UNREACHABLE = "vlm_unreachable"
ERR_FILE_MISSING = "file_missing"
ERR_DOCLING_FAILED = "docling_failed"
ERR_DOCLING_PARSE_FAILED = "docling_parse_failed"


def flag_low_confidence() -> str:
    return "low_confidence"


def flag_vlm_fallback() -> str:
    return "vlm_fallback"