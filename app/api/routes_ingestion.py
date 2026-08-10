from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.ingestion.doc_id import INITIAL_REVISION, generate_doc_id, is_valid_doc_id
from app.ingestion.job_state import JobState
from app.ingestion.schemas import RecStatus
from app.ingestion.repository import get_repository
from app.ingestion.tasks import run_ingestion_pipeline
from app.core.config import Settings
from app.ingestion.file_validation import validate_file_metadata
from app.pipeline.report import AnalysisReport, build_report, get_report_repository

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path(tempfile.gettempdir()) / "hr-anomaly-uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _upload_path(doc_id: str, original_name: str | None) -> Path:
    """Build a deterministic, sanitised on-disk path for an uploaded file.

    Keep the persisted source name opaque. Original filenames may contain
    employee or organization data and are not needed by the pipeline.
    """
    suffix = Path(original_name or "upload").suffix.lower()
    return UPLOAD_DIR / f"{doc_id}{suffix}"


@router.post("/upload")
async def upload_document(file: UploadFile) -> JobState:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename_required")
    doc_id = generate_doc_id()
    revision = INITIAL_REVISION
    dest = _upload_path(doc_id, file.filename)
    max_bytes = Settings().max_upload_size_bytes
    size = 0
    try:
        with dest.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    job = JobState(
                        doc_id=doc_id,
                        revision=revision,
                        statut=RecStatus.RED,
                        confiance=0.0,
                        flags=[],
                        erreur_traitement="file_too_large",
                    )
                    get_repository().save(job)
                    return job
                output.write(chunk)

        metadata = validate_file_metadata(dest, max_bytes=max_bytes)
        if not metadata.valid:
            job = JobState(
                doc_id=doc_id,
                revision=revision,
                statut=RecStatus.RED,
                confiance=0.0,
                flags=[],
                erreur_traitement=metadata.code,
            )
            get_repository().save(job)
            return job

        job = run_ingestion_pipeline(dest, doc_id, revision)
        repository = get_repository()
        repository.save(job)
        if get_report_repository().get(doc_id) is None:
            get_report_repository().save(_report_from_job(job))
        return job
    finally:
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            logger.warning("Unable to remove temporary upload %s", dest)
        await file.close()


def _report_from_job(job: JobState) -> AnalysisReport:
    class JobStage:
        doc_id = job.doc_id
        statut = job.statut
        record = object() if job.statut != RecStatus.RED else None
        erreur_traitement = job.erreur_traitement
        flags = tuple(flag.detail for flag in job.flags)
        anomaly_results: tuple[dict[str, object], ...] = ()

    return build_report(JobStage())


@router.get("/{doc_id}")
async def get_status(doc_id: str) -> JobState:
    if not is_valid_doc_id(doc_id):
        # Distinguish a malformed path segment (UUID-shaped only) from a
        # valid UUID that has no job attached — return 404 in both cases,
        # but the validation guards against path traversal lookups and
        # surfaces a clearer FastAPI error envelope than the lookup miss.
        raise HTTPException(status_code=404, detail="doc_id not found")
    job = get_repository().get(doc_id)
    if job is None:
        raise HTTPException(status_code=404, detail="doc_id not found")
    return job


@router.get("/{doc_id}/report", response_model=AnalysisReport)
async def get_report(doc_id: str) -> AnalysisReport:
    if not is_valid_doc_id(doc_id):
        raise HTTPException(status_code=404, detail="report_not_found")
    report = get_report_repository().get(doc_id)
    if report is None:
        job = get_repository().get(doc_id)
        if job is None:
            raise HTTPException(status_code=404, detail="report_not_found")
        report = _report_from_job(job)
        get_report_repository().save(report)
    return report