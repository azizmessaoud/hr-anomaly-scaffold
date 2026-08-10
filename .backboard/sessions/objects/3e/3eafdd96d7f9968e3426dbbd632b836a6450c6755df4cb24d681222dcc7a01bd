from __future__ import annotations

from app.ingestion.job_state import JobState
from app.ingestion.repository import IngestionJobRepository
from app.ingestion.schemas import RecStatus


def _job(doc_id: str = "550e8400-e29b-41d4-a716-446655440000") -> JobState:
    return JobState(
        doc_id=doc_id,
        revision=1,
        statut=RecStatus.GREEN,
        confiance=0.95,
        flags=[],
        erreur_traitement=None,
    )


def test_repository_save_and_get_returns_same_object():
    repo = IngestionJobRepository()
    job = _job()
    repo.save(job)
    fetched = repo.get(job.doc_id)

    assert fetched is job  # identity, not just equality


def test_repository_get_unknown_returns_none():
    repo = IngestionJobRepository()
    assert repo.get("nope") is None


def test_repository_save_overwrites_previous_entry():
    repo = IngestionJobRepository()
    doc_id = "550e8400-e29b-41d4-a716-446655440000"
    repo.save(_job(doc_id=doc_id))
    updated = JobState(
        doc_id=doc_id,
        revision=2,
        statut=RecStatus.AMBER,
        confiance=0.6,
        flags=[],
        erreur_traitement=None,
    )
    repo.save(updated)
    assert repo.get(doc_id) is updated


def test_repository_clear_removes_all_jobs():
    repo = IngestionJobRepository()
    repo.save(_job("550e8400-e29b-41d4-a716-446655440001"))
    repo.save(_job("550e8400-e29b-41d4-a716-446655440002"))
    repo.clear()
    assert repo.get("550e8400-e29b-41d4-a716-446655440001") is None
    assert repo.get("550e8400-e29b-41d4-a716-446655440002") is None