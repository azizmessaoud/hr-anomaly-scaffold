from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import ExtractPipelineConfig, Settings, make_extract_pipeline_config
from app.ingestion.doc_id import INITIAL_REVISION
from app.ingestion.docling_path import extract_from_docling
from app.ingestion.extraction_result import (
    ERR_DOCLING_FAILED,
    ERR_DOCLING_PARSE_FAILED,
    ERR_FILE_MISSING,
    ExtractionResult,
    flag_low_confidence,
)
from app.ingestion.job_state import (
    JobState,
    flags_from_strings,
    job_state_failed,
    job_state_from_record,
)
from app.ingestion.schemas import HRRecord, RecStatus
from app.ingestion.vlm_path import extract_with_vlm
from app.pipeline.status_composition import compose_status

logger = logging.getLogger(__name__)

_config: ExtractPipelineConfig | None = None


def _get_config() -> ExtractPipelineConfig:
    global _config
    if _config is None:
        _config = make_extract_pipeline_config(Settings())
    return _config


@dataclass(frozen=True)
class StageResult:
    doc_id: str
    revision: int
    terminal: bool = False
    statut: RecStatus | None = None
    record: dict[str, object] | None = None
    flags: tuple[str, ...] = ()
    erreur_traitement: str | None = None

    @classmethod
    def from_extraction(
        cls,
        result: ExtractionResult,
        *,
        doc_id: str,
        revision: int,
        statut: RecStatus,
    ) -> StageResult:
        if result.succeeded and result.record is not None:
            return cls(
                doc_id=doc_id,
                revision=revision,
                terminal=False,
                statut=statut,
                record=result.record.model_dump(mode="json"),
                flags=result.flags,
                erreur_traitement=None,
            )
        return cls(
            doc_id=doc_id,
            revision=revision,
            terminal=True,
            statut=RecStatus.RED,
            record=None,
            flags=result.flags,
            erreur_traitement=result.erreur_traitement,
        )


def _determine_extraction_status(
    result: ExtractionResult,
    threshold: float,
) -> RecStatus:
    if not result.succeeded or result.record is None:
        return RecStatus.RED
    record = result.record
    if result.source == "docling" and result.confidence < threshold:
        return RecStatus.AMBER
    if any(
        flag.moteur == result.source and "manquant" in flag.detail
        for flag in record.flags
    ):
        return RecStatus.AMBER
    return RecStatus.GREEN


def ingest_document(
    document_path: Path,
    doc_id: str,
    revision: int = 0,
) -> StageResult:
    if not document_path.exists():
        return StageResult(
            doc_id=doc_id,
            revision=revision,
            terminal=True,
            statut=RecStatus.RED,
            erreur_traitement=ERR_FILE_MISSING,
        )
    return StageResult(doc_id=doc_id, revision=revision)


def _needs_vlm_fallback(result: ExtractionResult, threshold: float) -> bool:
    if not result.succeeded:
        return True
    return result.confidence < threshold


def _combine_flags(*sources: tuple[str, ...]) -> tuple[str, ...]:
    seen: list[str] = []
    for src in sources:
        for flag in src:
            if flag not in seen:
                seen.append(flag)
    return tuple(seen)


def extract_fields(
    document_path: Path,
    doc_id: str,
    revision: int = 0,
) -> StageResult:
    config = _get_config()
    threshold = config.docling_confidence_threshold

    docling_failure_reason: str | None = None
    try:
        docling_result = extract_from_docling(
            document_path,
            doc_id=doc_id,
            revision=revision,
            config=config,
        )
    except Exception as exc:
        logger.warning("Docling failed for %s: %s", doc_id, exc)
        docling_result = ExtractionResult(
            record=None,
            confidence=0.0,
            source="docling",
            flags=(),
            erreur_traitement=ERR_DOCLING_FAILED,
        )
        docling_failure_reason = f"{ERR_DOCLING_FAILED}:{type(exc).__name__}"

    if docling_result.succeeded and not _needs_vlm_fallback(docling_result, threshold):
        extraction_status = _determine_extraction_status(docling_result, threshold)
        return StageResult.from_extraction(
            docling_result,
            doc_id=doc_id,
            revision=revision,
            statut=extraction_status,
        )

    fallback_reason = (
        ERR_DOCLING_FAILED
        if docling_failure_reason is not None
        else f"{flag_low_confidence()}:{docling_result.confidence:.2f}"
    )
    vlm_result = extract_with_vlm(
        document_path,
        doc_id=doc_id,
        revision=revision,
        config=config,
    )

    if vlm_result.succeeded and vlm_result.record is not None:
        extraction_status = _determine_extraction_status(vlm_result, threshold)
        return StageResult.from_extraction(
            vlm_result,
            doc_id=doc_id,
            revision=revision,
            statut=extraction_status,
        )

    reasons: list[str] = []
    if docling_failure_reason is not None:
        reasons.append(docling_failure_reason)
    elif docling_result.succeeded:
        reasons.append(fallback_reason)
    if vlm_result.erreur_traitement is not None:
        reasons.append(vlm_result.erreur_traitement)

    detail = f"{ERR_DOCLING_PARSE_FAILED}:{'|'.join(reasons) or 'unknown'}"
    return StageResult(
        doc_id=doc_id,
        revision=revision,
        terminal=True,
        statut=RecStatus.RED,
        flags=_combine_flags(
            docling_result.flags,
            vlm_result.flags,
            (flag_low_confidence(),),
        ),
        erreur_traitement=detail,
    )


def validate_record(stage: StageResult) -> StageResult:
    if stage.terminal:
        return stage

    if stage.record is None:
        return StageResult(
            doc_id=stage.doc_id,
            revision=stage.revision,
            terminal=True,
            statut=RecStatus.RED,
            flags=stage.flags,
            erreur_traitement="validation_failed:no_record",
        )

    try:
        record = HRRecord(**stage.record)
    except Exception as exc:
        return StageResult(
            doc_id=stage.doc_id,
            revision=stage.revision,
            terminal=True,
            statut=RecStatus.RED,
            flags=stage.flags,
            erreur_traitement=f"validation_failed:{type(exc).__name__}",
        )

    validation_status = RecStatus.GREEN
    final_status = compose_status(stage.statut if stage.statut is not None else RecStatus.RED, validation_status)

    return StageResult(
        doc_id=stage.doc_id,
        revision=stage.revision,
        terminal=True,
        statut=final_status,
        record=record.model_dump(mode="json"),
        flags=stage.flags,
        erreur_traitement=record.erreur_traitement,
    )


def stage_to_job_state(stage: StageResult) -> JobState:
    pipeline_flags = flags_from_strings(stage.flags)
    if stage.record is not None:
        record_dict = dict(stage.record)
        if stage.statut is not None:
            record_dict["statut"] = stage.statut
        record = HRRecord(**record_dict)
        merged = record.flags + pipeline_flags
        return job_state_from_record(
            record,
            doc_id=stage.doc_id,
            revision=stage.revision,
            flags_override=merged,
            erreur_traitement_override=stage.erreur_traitement,
        )
    return job_state_failed(
        doc_id=stage.doc_id,
        revision=stage.revision,
        erreur_traitement=stage.erreur_traitement or "traitement echoue",
        flags=pipeline_flags,
    )


def run_ingestion_pipeline(
    document_path: Path,
    doc_id: str,
    revision: int = INITIAL_REVISION,
) -> JobState:
    ingest_stage = ingest_document(document_path, doc_id, revision)
    if ingest_stage.terminal:
        return stage_to_job_state(ingest_stage)

    extract_stage = extract_fields(document_path, doc_id, revision)
    if extract_stage.terminal:
        return stage_to_job_state(extract_stage)

    validate_stage = validate_record(extract_stage)
    return stage_to_job_state(validate_stage)