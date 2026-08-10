from __future__ import annotations

from app.ingestion.schemas import RecStatus


def compose_status(extraction: RecStatus, validation: RecStatus) -> RecStatus:
    if extraction == RecStatus.RED or validation == RecStatus.RED:
        return RecStatus.RED
    if extraction == RecStatus.AMBER or validation == RecStatus.AMBER:
        return RecStatus.AMBER
    return RecStatus.GREEN