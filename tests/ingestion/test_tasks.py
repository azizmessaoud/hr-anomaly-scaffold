from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.doc_id import INITIAL_REVISION
from app.ingestion.extraction_result import (
    ERR_DOCLING_FAILED,
    ERR_FILE_MISSING,
    ERR_RAPIDOCR_MISSING_REQUIRED_FIELD,
    ERR_RAPIDOCR_NO_TEXT,
    ERR_RAPIDOCR_UNREACHABLE,
    ExtractionResult,
    flag_docling_low_confidence_review,
    flag_rapidocr_disabled_in_env,
    flag_rapidocr_fallback,
    flag_rapidocr_unreachable,
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
from app.core.config import ExtractPipelineConfig, Settings, make_extract_pipeline_config
import app.ingestion.tasks as tasks_module


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


def _rapidocr_result(
    *,
    statut: RecStatus = RecStatus.GREEN,
    confidence: float = 0.5,
    doc_id: str = "doc-x",
    record: HRRecord | None = None,
    flags: tuple[str, ...] = (),
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
        source="rapidocr",
        flags=flags if flags else (flag_rapidocr_fallback(),),
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
# extract_fields — Docling-first with RapidOCR fallback
# ---------------------------------------------------------------------------


def test_extract_fields_high_confidence_docling_no_fallback(fake_document: Path):
    """Docling >= threshold => no RapidOCR call, no fallback flag, GREEN."""

    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.GREEN, confidence=0.95
        )
    )
    rapidocr_mock = MagicMock()

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is False
    assert stage.statut == RecStatus.GREEN
    assert rapidocr_mock.call_count == 0


def test_extract_fields_low_confidence_docling_triggers_rapidocr(fake_document: Path):
    """Below-threshold Docling => RapidOCR fallback fires; result keeps
    ``rapidocr_fallback`` flag, status is AMBER at minimum.
    """
    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER, confidence=0.45
        )
    )
    rapidocr_mock = MagicMock(
        return_value=_rapidocr_result(statut=RecStatus.GREEN, confidence=0.6)
    )

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert rapidocr_mock.call_count == 1
    assert stage.terminal is False
    assert flag_rapidocr_fallback() in stage.flags


def test_extract_fields_missing_fields_high_confidence_triggers_rapidocr(fake_document: Path):
    """High-confidence Docling but with missing required fields => RapidOCR fallback fires.
    This is the core bug fix: missing fields should trigger the rescue path even
    when Docling's confidence score is high. Without this, incomplete extractions
    silently return AMBER without attempting the fallback.
    """
    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER,
            confidence=0.95,  # high confidence
            missing=["date_embauche", "salaire_brut"],  # shared payroll completeness fields
        )
    )
    rapidocr_mock = MagicMock(
        return_value=_rapidocr_result(statut=RecStatus.GREEN, confidence=0.6)
    )

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert rapidocr_mock.call_count == 1, (
        "RapidOCR should be called when Docling has missing required fields, "
        "regardless of confidence score"
    )
    assert stage.terminal is False
    assert flag_rapidocr_fallback() in stage.flags


def test_extract_fields_docling_failure_triggers_rapidocr(fake_document: Path):
    """Docling raised => RapidOCR runs; if RapidOCR succeeds, record is propagated."""
    failing_docling = MagicMock(side_effect=RuntimeError("boom"))
    rapidocr_mock = MagicMock(
        return_value=_rapidocr_result(statut=RecStatus.GREEN, confidence=0.6)
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert rapidocr_mock.call_count == 1
    assert stage.terminal is False
    assert flag_rapidocr_fallback() in stage.flags


def test_extract_fields_both_paths_fail_returns_red(fake_document: Path):
    """Docling failure + RapidOCR failure => RED with both reasons surfaced.
    The previously successful Docling record (if any) must NOT be silently
    substituted.
    """
    failing_docling = MagicMock(side_effect=RuntimeError("d1"))
    failing_rapidocr = MagicMock(
        return_value=_rapidocr_result(
            record=None,
            erreur_traitement=ERR_RAPIDOCR_NO_TEXT,
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_rapidocr", failing_rapidocr):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is True
    assert stage.statut == RecStatus.RED
    assert stage.erreur_traitement is not None
    assert ERR_DOCLING_FAILED in stage.erreur_traitement
    assert ERR_RAPIDOCR_NO_TEXT in stage.erreur_traitement


def test_extract_fields_low_confidence_docling_rapidocr_failure_preserves_docling_as_amber(fake_document: Path):
    """Low-confidence Docling + RapidOCR missing-required-field => AMBER (not RED).

    Spec: 'Keep the best available extraction.' Docling success + RapidOCR
    failure must NOT overwrite the Docling record with a RED terminal.
    The record stays in the review queue, flagged ``rapidocr_unreachable`` so
    the reviewer knows it's a connectivity problem, not a content one.
    """
    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER, confidence=0.45
        )
    )
    rapidocr_mock = MagicMock(
        return_value=_rapidocr_result(
            record=None,
            erreur_traitement=ERR_RAPIDOCR_UNREACHABLE,
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is False
    assert stage.statut == RecStatus.AMBER
    assert stage.record is not None
    assert stage.record["nom"] == "A"
    assert "rapidocr_unreachable" in stage.flags
    assert "docling_low_confidence_review" in stage.flags


def test_extract_fields_low_confidence_docling_rapidocr_missing_field_no_unreachable_flag(
    fake_document: Path,
) -> None:
    """When Docling is low-confidence and RapidOCR fails with missing field error
    (not unreachable), the ``rapidocr_unreachable`` flag should NOT be added."""
    from app.ingestion.extraction_result import ERR_RAPIDOCR_MISSING_REQUIRED_FIELD
    from app.ingestion.tasks import extract_fields
    from app.ingestion.job_state import RecStatus

    docling_mock = MagicMock(
        return_value=_docling_result(
            confidence=0.35,
            flags=("docling_low_confidence_review",),
        )
    )
    rapidocr_mock = MagicMock(
        return_value=_rapidocr_result(
            record=None,
            erreur_traitement=f"{ERR_RAPIDOCR_MISSING_REQUIRED_FIELD}:cin",
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is False
    assert stage.statut == RecStatus.AMBER
    assert stage.record is not None
    assert "rapidocr_unreachable" not in stage.flags
    assert "docling_low_confidence_review" in stage.flags


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
    assert result.terminal is False


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
    assert result.terminal is False


def test_pipeline_runs_advisory_anomaly_detection_after_validation(fake_document: Path):
    """Successful validation must remain eligible for anomaly detection."""
    docling = MagicMock(return_value=_docling_result())

    with patch("app.ingestion.tasks.extract_from_docling", docling):
        with patch("app.anomalies.orchestrator.detect_anomalies") as detect:
            detect.side_effect = lambda stage: stage
            job = run_ingestion_pipeline(fake_document, "doc-x")

    detect.assert_called_once()
    assert job.statut == RecStatus.GREEN


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
    failing_rapidocr = MagicMock(
        return_value=_rapidocr_result(
            record=None, erreur_traitement=ERR_RAPIDOCR_NO_TEXT
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_rapidocr", failing_rapidocr):
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
        flags=("rapidocr_fallback", "low_confidence"),
        erreur_traitement="both_failed",
    )
    job = stage_to_job_state(stage)

    flag_details = [flag.detail for flag in job.flags]
    assert "rapidocr_fallback" in flag_details
    assert "low_confidence" in flag_details
    assert job.erreur_traitement == "both_failed"


# ---------------------------------------------------------------------------
# doc_id + revision contract
# ---------------------------------------------------------------------------


def test_revision_defaults_to_initial_revision_in_pipeline(fake_document: Path):
    """If the pipeline is called without an explicit revision, it defaults
    to ``INITIAL_REVISION`` (1) and the resulting JobState surfaces it."""
    failing_docling = MagicMock(side_effect=RuntimeError("d1"))
    failing_rapidocr = MagicMock(
        return_value=_rapidocr_result(
            record=None, erreur_traitement=ERR_RAPIDOCR_NO_TEXT
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", failing_docling):
        with patch("app.ingestion.tasks.extract_with_rapidocr", failing_rapidocr):
            job = run_ingestion_pipeline(fake_document, "doc-x")

    assert job.revision == INITIAL_REVISION


# ---------------------------------------------------------------------------
# Canonical flag vocabulary — fallback policy (per docs/runtime.md)
# ---------------------------------------------------------------------------


def _stub_config(rapidocr_enabled: bool) -> ExtractPipelineConfig:
    """Return a deterministic ExtractPipelineConfig for a given RapidOCR mode."""
    base = Settings()
    cfg = make_extract_pipeline_config(base).model_copy(
        update={"rapidocr_enabled": rapidocr_enabled}
    )
    return cfg


@pytest.fixture(autouse=False)
def reset_config_cache():
    """Reset the cached config inside tasks.py between tests.

    The module caches ``_config`` on first call; without resetting, tests
    that mutate the config (e.g. toggling ``rapidocr_enabled``) leak state
    into subsequent tests."""
    tasks_module._config = None
    yield
    tasks_module._config = None


def test_rapidocr_disabled_preserves_low_confidence_docling_with_amber_and_flag(
    fake_document: Path, reset_config_cache
):
    """``RAPIDOCR_ENABLED=false`` + low-confidence Docling => AMBER, not RED.

    The Docling record is preserved (best-available extraction policy),
    ``rapidocr_disabled_in_env`` surfaces the intentional config choice, and
    ``docling_low_confidence_review`` flags the human-judgment gate.
    """
    tasks_module._config = _stub_config(rapidocr_enabled=False)

    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER, confidence=0.45
        )
    )
    rapidocr_mock = MagicMock()

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert rapidocr_mock.call_count == 0
    assert stage.terminal is False
    assert stage.statut == RecStatus.AMBER
    assert stage.record is not None
    assert flag_rapidocr_disabled_in_env() in stage.flags
    assert flag_docling_low_confidence_review() in stage.flags


def test_rapidocr_unreachable_preserves_low_confidence_docling_with_amber(
    fake_document: Path, reset_config_cache
):
    """Docling low-confidence + RapidOCR engine unavailable => AMBER (not RED).

    Reviewer-visible flags: ``rapidocr_unreachable`` (engine not importable) and
    ``docling_low_confidence_review`` (Docling below threshold).
    """
    tasks_module._config = _stub_config(rapidocr_enabled=True)

    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER, confidence=0.45
        )
    )
    rapidocr_mock = MagicMock(
        return_value=_rapidocr_result(
            record=None,
            erreur_traitement=ERR_RAPIDOCR_UNREACHABLE,
            flags=(flag_rapidocr_unreachable(),),
        )
    )

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert stage.terminal is False
    assert stage.statut == RecStatus.AMBER
    assert stage.record is not None
    assert flag_rapidocr_unreachable() in stage.flags
    assert flag_docling_low_confidence_review() in stage.flags


def test_rapidocr_disabled_full_confidence_docling_returns_amber_when_incomplete(
    fake_document: Path, reset_config_cache
):
    """``RAPIDOCR_ENABLED=false`` + high-confidence Docling missing required fields
    => AMBER with the existing manquant flag intact. No spurious
    ``rapidocr_unreachable`` flag (RapidOCR wasn't unreachable; it was disabled).
    """
    tasks_module._config = _stub_config(rapidocr_enabled=False)

    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.AMBER,
            confidence=0.95,
            missing=["date_embauche", "salaire_brut"],
        )
    )
    rapidocr_mock = MagicMock()

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert rapidocr_mock.call_count == 0
    assert stage.terminal is False
    assert stage.statut == RecStatus.AMBER
    assert stage.record is not None
    assert flag_rapidocr_disabled_in_env() in stage.flags
    assert flag_rapidocr_unreachable() not in stage.flags


def test_high_confidence_complete_docling_with_rapidocr_disabled_returns_green(
    fake_document: Path, reset_config_cache
):
    """``RAPIDOCR_ENABLED=false`` + clean high-confidence Docling => GREEN, no
    fallback flags. Sanity check: the disable path doesn't artificially
    downgrade clean records."""
    tasks_module._config = _stub_config(rapidocr_enabled=False)

    docling_mock = MagicMock(
        return_value=_docling_result(
            statut=RecStatus.GREEN, confidence=0.95
        )
    )
    rapidocr_mock = MagicMock()

    with patch("app.ingestion.tasks.extract_from_docling", docling_mock):
        with patch("app.ingestion.tasks.extract_with_rapidocr", rapidocr_mock):
            stage = extract_fields(fake_document, "doc-x")

    assert rapidocr_mock.call_count == 0
    assert stage.terminal is False
    assert stage.statut == RecStatus.GREEN
    assert flag_rapidocr_disabled_in_env() not in stage.flags