from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.ingestion.doc_id import INITIAL_REVISION, generate_doc_id, is_valid_doc_id
from app.ingestion.job_state import JobState
from app.ingestion.repository import get_repository
from app.ingestion.tasks import run_ingestion_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path(tempfile.gettempdir()) / "hr-anomaly-uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _upload_path(doc_id: str, original_name: str | None) -> Path:
    """Build a deterministic, sanitised on-disk path for an uploaded file.

    The doc_id is the only piece of the filename that comes from our
    pipeline; the original name is preserved as a suffix for operator
    debuggability only. ``Path.name`` is sanitised against path
    separators before use.
    """
    suffix = Path(original_name or "upload").name
    return UPLOAD_DIR / f"{doc_id}_{suffix}"


@router.post("/upload")
async def upload_document(file: UploadFile) -> JobState:
    doc_id = generate_doc_id()
    revision = INITIAL_REVISION
    dest = _upload_path(doc_id, file.filename)
    content = await file.read()
    dest.write_bytes(content)

    job = run_ingestion_pipeline(dest, doc_id, revision)
    repository = get_repository()
    repository.save(job)
    return job


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