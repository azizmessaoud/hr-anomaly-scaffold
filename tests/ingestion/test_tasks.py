from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.doc_id import INITIAL_REVISION
from app.ingestion.extraction_result import (
    ERR_DOCLING_FAILED,
    ERR_FILE_MISSING,
    ERR_VLM_MALFORMED_JSON,
    ERR_VLM_MISSING_REQUIRED_FIELD,
    ExtractionResult,
    flag_vlm_fallback,
)
from app.ingestion.job_state import JobState
from app.ingestion.schemas import HRRecord, RecStatus
from app.ingestion.tasks import (
    extract_fields,
    ingest_document,
    run_ingestion_pipeline,
    stage_to_job_state,
    validate_record,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_document(tmp_path: Path) -> Path:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    return pdf


def _docling_result(
    *,
    statut: RecStatus = RecStatus.GREEN,
    confidence: float = 0.95,
    doc_id: str = "doc-x",
    flags: tuple[str, ...] = (),
    missing: list[str] | None = None,
) -> ExtractionResult:
    """Build a synthetic successful ExtractionResult as Docling would emit."""
    hr = HRRecord(
        id=doc_id,
        revision=INITIAL_REVISION,
        nom="A",
        prenom="B",
        cin="AB123456",
        cnss="123456789",
        date_embauche="2020-01-01",
        salaire_brut=1000.0,
        confiance=confidence,
        statut=statut,
    )
    if missing:
        for name in missing:
            setattr(hr, name, None)
    return ExtractionResult(
        record=hr, confidence=confidence, source="docling", flags=flags
    )


def _vlm_result(
    *,
    statut: RecStatus = RecStatus.GREEN,
    confidence: float = 0.5,
    doc_id: str = "doc-x",
    record: HRRecord | None = None,
    erreur_traitement: str | None = None,
) -> ExtractionResult:
    if record is None and erreur_traitement is None:
        record = HRRecord(
            id=doc_id,
            revision=INITIAL_REVISION,
            nom="A",
            prenom="B",
            cin="AB123456",
            cnss="123456789",
            date_embauche="2020-01-01",
            salaire_brut=1000.0,
            confiance=confidence,
            statut=statut,
        )
    return ExtractionResult(
        record=record,
        confidence=confidence,
        source="vlm",
        flags=(flag_vlm_fallback(),),
        erreur_traitement=erreur_traitement,
    )


# ---------------------------------------------------------------------------
# ingest_document — file existence gate
# ---------------------------------------------------------------------------


def test_ingest_document_missing_file_returns_red(fake_document: Path):
    missing = fake_document.with_name("ghost.pdf")
    stage = ingest_document(missing, "doc-x")

    assert stage.terminal is True
    assert stage.statut == RecStatus.RED
    assert stage.erreur_traitement == ERR_FILE_MISSING


def test_ingest_document_existing_file_returns_open_stage(fake_document: Path):
    stage = ingest_document(fake_document, "doc-x")

    assert stage.terminal is False
    assert stage.statut is None
    assert stage.erreur_traitement is None


# ---------------------------------------------------------------------------
# extract_fields — Docling-first with VLM fallback
# ---------------------------------------------------------------------------


def test_extract_fields_high_confidence_docling_no_fallback(fake_document: Path):
    """Docling >= threshold => no VLM call, no fallback flag, GREEN."""

    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.GREEN, confidence=0.95
        )
    )
    vlm_mock = MagicMock()

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_vlm", vlm_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is False
    assert stage.statut == RecStatus.GREEN
    assert vlm_mock.call_count == 0


def test_extract_fields_low_confidence_docling_triggers_vlm(fake_document: Path):
    """Below-threshold Docling => VLM fallback fires; result keeps
    ``vlm_fallback`` flag, status is AMBER at minimum.
    """
    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER, confidence=0.45
        )
    )
    vlm_mock = MagicMock(
        return_value=_vlm_result(statut=RecStatus.GREEN, confidence=0.6)
    )

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_vlm", vlm_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert vlm_mock.call_count == 1
    assert stage.terminal is False
    assert flag_vlm_fallback() in stage.flags


def test_extract_fields_docling_failure_triggers_vlm(fake_document: Path):
    """Docling raised => VLM runs; if VLM succeeds, record is propagated."""
    failing_docling = MagicMock(side_effect=RuntimeError("boom"))
    vlm_mock = MagicMock(
        return_value=_vlm_result(statut=RecStatus.GREEN, confidence=0.6)
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_vlm", vlm_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert vlm_mock.call_count == 1
    assert stage.terminal is False
    assert flag_vlm_fallback() in stage.flags


def test_extract_fields_both_paths_fail_returns_red(fake_document: Path):
    """Docling failure + VLM failure => RED with both reasons surfaced.
    The previously successful Docling record (if any) must NOT be silently
    substituted.
    """
    failing_docling = MagicMock(side_effect=RuntimeError("d1"))
    failing_vlm = MagicMock(
        return_value=_vlm_result(
            record=None,
            erreur_traitement=ERR_VLM_MALFORMED_JSON,
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_vlm", failing_vlm):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is True
    assert stage.statut == RecStatus.RED
    assert stage.erreur_traitement is not None
    assert ERR_DOCLING_FAILED in stage.erreur_traitement
    assert ERR_VLM_MALFORMED_JSON in stage.erreur_traitement


def test_extract_fields_low_confidence_vlm_failure_returns_red(fake_document: Path):
    """Low-confidence Docling + VLM missing-required-field => RED.
    The fact that Docling 'succeeded' with low confidence must NOT be
    enough to mask a VLM failure.
    """
    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER, confidence=0.45
        )
    )
    vlm_mock = MagicMock(
        return_value=_vlm_result(
            record=None,
            erreur_traitement=f"{ERR_VLM_MISSING_REQUIRED_FIELD}:cin,cnss",
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_vlm", vlm_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is True
    assert stage.statut == RecStatus.RED
    assert stage.erreur_traitement is not None
    assert ERR_VLM_MISSING_REQUIRED_FIELD in stage.erreur_traitement


# ---------------------------------------------------------------------------
# validate_record — no AMBER → GREEN promotion, RED is sticky
# ---------------------------------------------------------------------------


def _stage_from_record_dict(record: HRRecord, **overrides) -> "object":
    """Wrap an HRRecord dict into a StageResult-like object for validate_record."""
    from app.ingestion.tasks import StageResult

    payload = record.model_dump(mode="json")
    payload.pop("flags", None)  # flags live on the StageResult, not on record
    defaults = dict(
        doc_id=record.id,
        revision=record.revision,
        terminal=False,
        statut=record.statut,
        record=payload,
        flags=(),
        erreur_traitement=None,
    )
    defaults.update(overrides)
    return StageResult(**defaults)


def test_validate_record_does_not_promote_amber_to_green():
    """Locked rule: validation never elevates AMBER to GREEN."""
    amber_record = HRRecord(
        id="doc-x",
        revision=INITIAL_REVISION,
        nom="A",
        cin="AB123456",
        cnss="123456789",
        date_embauche="2020-01-01",
        salaire_brut=1000.0,
        confiance=0.5,
        statut=RecStatus.AMBER,
    )
    stage = _stage_from_record_dict(amber_record, statut=RecStatus.AMBER)
    result = validate_record(stage)  # type: ignore[arg-type]

    assert result.statut == RecStatus.AMBER, (
        "AMBER must NOT be promoted to GREEN by validation"
    )
    assert result.terminal is True


def test_validate_record_keeps_green_when_record_is_well_formed():
    record = HRRecord(
        id="doc-x",
        revision=INITIAL_REVISION,
        nom="A",
        cin="AB123456",
        cnss="123456789",
        date_embauche="2020-01-01",
        salaire_brut=1000.0,
        confiance=0.95,
        statut=RecStatus.GREEN,
    )
    stage = _stage_from_record_dict(record, statut=RecStatus.GREEN)
    result = validate_record(stage)  # type: ignore[arg-type]

    assert result.statut == RecStatus.GREEN


def test_validate_record_red_stage_is_sticky():
    """RED is sticky: validation does not rescue it."""
    from app.ingestion.tasks import StageResult

    stage = StageResult(
        doc_id="doc-x",
        revision=INITIAL_REVISION,
        terminal=True,
        statut=RecStatus.RED,
        record=None,
        flags=(),
        erreur_traitement="already_red",
    )
    result = validate_record(stage)

    assert result.statut == RecStatus.RED
    assert result.erreur_traitement == "already_red"


def test_validate_record_bad_payload_returns_red():
    from app.ingestion.tasks import StageResult

    # ``id`` is a required field on HRRecord, so omitting it makes
    # Pydantic raise. The orchestrator must catch that and turn it into
    # a typed RED with an explicit reason.
    stage = StageResult(
        doc_id="doc-x",
        revision=INITIAL_REVISION,
        terminal=False,
        statut=None,
        record={"nom": "A"},  # missing required ``id`` -> Pydantic raises
        flags=(),
        erreur_traitement=None,
    )
    result = validate_record(stage)

    assert result.terminal is True
    assert result.statut == RecStatus.RED
    assert result.erreur_traitement is not None
    assert result.erreur_traitement.startswith("validation_failed:")


# ---------------------------------------------------------------------------
# run_ingestion_pipeline + stage_to_job_state — full chain
# ---------------------------------------------------------------------------


def test_run_pipeline_red_path_produces_job_state(fake_document: Path):
    failing_docling = MagicMock(side_effect=RuntimeError("d1"))
    failing_vlm = MagicMock(
        return_value=_vlm_result(
            record=None, erreur_traitement=ERR_VLM_MALFORMED_JSON
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_vlm", failing_vlm):
            job = run_ingestion_pipeline(fake_document, "doc-x")

    assert isinstance(job, JobState)
    assert job.statut == RecStatus.RED
    assert job.erreur_traitement is not None
    assert job.revision == INITIAL_REVISION


def test_stage_to_job_state_red_path_uses_pipeline_flags():
    from app.ingestion.tasks import StageResult

    stage = StageResult(
        doc_id="doc-x",
        revision=INITIAL_REVISION,
        terminal=True,
        statut=RecStatus.RED,
        record=None,
        flags=("vlm_fallback", "low_confidence"),
        erreur_traitement="both_failed",
    )
    job = stage_to_job_state(stage)

    flag_details = [flag.detail for flag in job.flags]
    assert "vlm_fallback" in flag_details
    assert "low_confidence" in flag_details
    assert job.erreur_traitement == "both_failed"


# ---------------------------------------------------------------------------
# doc_id + revision contract
# ---------------------------------------------------------------------------


def test_revision_defaults_to_initial_revision_in_pipeline(fake_document: Path):
    """If the pipeline is called without an explicit revision, it defaults
    to ``INITIAL_REVISION`` (1) and the resulting JobState surfaces it."""
    failing_docling = MagicMock(side_effect=RuntimeError("d1"))
    failing_vlm = MagicMock(
        return_value=_vlm_result(
            record=None, erreur_traitement=ERR_VLM_MALFORMED_JSON
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_vlm", failing_vlm):
            job = run_ingestion_pipeline(fake_document, "doc-x")

    assert job.revision == INITIAL_REVISION