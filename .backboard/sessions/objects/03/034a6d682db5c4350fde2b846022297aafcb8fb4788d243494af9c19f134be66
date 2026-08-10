from __future__ import annotations

import pytest

from app.ingestion.schemas import RecStatus
from app.pipeline.status_composition import compose_status


@pytest.mark.parametrize(
    "extraction,validation,expected",
    [
        (RecStatus.GREEN, RecStatus.GREEN, RecStatus.GREEN),
        (RecStatus.GREEN, RecStatus.AMBER, RecStatus.AMBER),
        (RecStatus.GREEN, RecStatus.RED, RecStatus.RED),
        (RecStatus.AMBER, RecStatus.GREEN, RecStatus.AMBER),
        (RecStatus.AMBER, RecStatus.AMBER, RecStatus.AMBER),
        (RecStatus.AMBER, RecStatus.RED, RecStatus.RED),
        (RecStatus.RED, RecStatus.GREEN, RecStatus.RED),
        (RecStatus.RED, RecStatus.AMBER, RecStatus.RED),
        (RecStatus.RED, RecStatus.RED, RecStatus.RED),
    ],
)
def test_compose_status(extraction: RecStatus, validation: RecStatus, expected: RecStatus) -> None:
    assert compose_status(extraction, validation) == expected


def test_compose_status_red_is_sticky_under_extraction_failure() -> None:
    assert compose_status(RecStatus.RED, RecStatus.GREEN) == RecStatus.RED


def test_compose_status_red_is_sticky_under_validation_failure() -> None:
    assert compose_status(RecStatus.GREEN, RecStatus.RED) == RecStatus.RED


def test_compose_status_amber_preserved_when_both_amber() -> None:
    assert compose_status(RecStatus.AMBER, RecStatus.AMBER) == RecStatus.AMBER


def test_compose_status_amber_preserved_when_only_extraction_amber() -> None:
    assert compose_status(RecStatus.AMBER, RecStatus.GREEN) == RecStatus.AMBER


def test_compose_status_amber_preserved_when_only_validation_amber() -> None:
    assert compose_status(RecStatus.GREEN, RecStatus.AMBER) == RecStatus.AMBER