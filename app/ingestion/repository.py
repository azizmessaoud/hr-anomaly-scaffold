from __future__ import annotations

from app.ingestion.job_state import JobState


class IngestionJobRepository:
    """In-memory job store; swap for Postgres in Layer 5."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}

    def save(self, job: JobState) -> None:
        self._jobs[job.doc_id] = job

    def get(self, doc_id: str) -> JobState | None:
        return self._jobs.get(doc_id)

    def clear(self) -> None:
        self._jobs.clear()


_default_repository = IngestionJobRepository()


def get_repository() -> IngestionJobRepository:
    return _default_repository
