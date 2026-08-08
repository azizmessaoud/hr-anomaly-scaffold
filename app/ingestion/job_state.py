from __future__ import annotations

from pydantic import BaseModel, Field

from app.ingestion.schemas import Flag, HRRecord, RecStatus


class JobState(BaseModel):
    """Pollable ingestion job payload returned by the API.

    Six-field contract: ``doc_id``, ``revision``, ``statut``, ``confiance``,
    ``flags``, ``erreur_traitement``. Both ``POST /ingest/upload`` and
    ``GET /ingest/{doc_id}`` return this same model.
    """

    doc_id: str
    revision: int = Field(default=1, ge=1)
    statut: RecStatus
    confiance: float = Field(default=0.0, ge=0.0, le=1.0)
    flags: list[Flag] = Field(default_factory=list)
    erreur_traitement: str | None = None


def job_state_from_record(
    record: HRRecord,
    *,
    doc_id: str,
    revision: int,
    flags_override: list[Flag] | None = None,
    erreur_traitement_override: str | None = None,
) -> JobState:
    """Project an ``HRRecord`` onto the public ``JobState`` contract.

    ``flags_override`` lets the orchestrator carry forward flags that the
    extractor surfaced (e.g. ``rapidocr_fallback``) without forcing those flags
    into the ``HRRecord`` model itself. ``erreur_traitement_override`` is
    used when the orchestrator-level error message supersedes the
    per-record one.
    """
    return JobState(
        doc_id=doc_id,
        revision=revision,
        statut=record.statut,
        confiance=record.confiance,
        flags=flags_override if flags_override is not None else record.flags,
        erreur_traitement=(
            erreur_traitement_override
            if erreur_traitement_override is not None
            else record.erreur_traitement
        ),
    )


def job_state_failed(
    *,
    doc_id: str,
    revision: int,
    erreur_traitement: str,
    flags: list[Flag] | None = None,
) -> JobState:
    return JobState(
        doc_id=doc_id,
        revision=revision,
        statut=RecStatus.RED,
        confiance=0.0,
        flags=flags or [],
        erreur_traitement=erreur_traitement,
    )


def flags_from_strings(raw: tuple[str, ...] | list[str]) -> list[Flag]:
    """Map orchestrator-level string flags to ``Flag`` objects on the wire.

    The orchestrator (``tasks.py``) carries extractor flags as plain strings
    (``"rapidocr_fallback"``, ``"low_confidence"``) to avoid coupling the
    pipeline to ``Flag`` shape. When projecting to ``JobState`` for the
    API, those become ``Flag(moteur="pipeline", detail=<flag>)`` rows so
    the existing dashboard renderer keeps working.
    """
    return [
        Flag(moteur="pipeline", detail=name)
        for name in raw
    ]