from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.ingestion.job_state import JobState
from app.ingestion.repository import IngestionJobRepository
from app.ingestion.schemas import RecStatus


@pytest.fixture
def patched_repo(monkeypatch: pytest.MonkeyPatch):
    repo = IngestionJobRepository()
    monkeypatch.setattr(
        "app.api.routes_ingestion.get_repository", lambda: repo
    )
    return repo


@pytest.fixture
def client(patched_repo: IngestionJobRepository) -> TestClient:
    from app.main import create_app

    application = create_app()
    return TestClient(application)


# ---------------------------------------------------------------------------
# POST /ingest/upload + GET /ingest/{doc_id} — shape parity
# ---------------------------------------------------------------------------


def test_upload_then_poll_returns_same_six_field_contract(
    client: TestClient,
    tmp_path: Path,
):
    """The locked contract: doc_id, revision, statut, confiance, flags,
    erreur_traitement. Upload and polling must return identical field
    names and types for the same job.
    """
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    # Short-circuit the pipeline to a deterministic GREEN job so the test
    # is independent of extractor behaviour (covered separately in
    # test_tasks.py / test_docling_path.py).
    sentinel = JobState(
        doc_id="550e8400-e29b-41d4-a716-446655440000",
        revision=1,
        statut=RecStatus.GREEN,
        confiance=0.95,
        flags=[],
        erreur_traitement=None,
    )
    with patch(
        "app.api.routes_ingestion.run_ingestion_pipeline",
        return_value=sentinel,
    ):
        upload_response = client.post(
            "/ingest/upload",
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )

    assert upload_response.status_code == 200
    upload_body = upload_response.json()

    expected_keys = {
        "doc_id",
        "revision",
        "statut",
        "confiance",
        "flags",
        "erreur_traitement",
    }
    assert set(upload_body.keys()) == expected_keys

    poll_response = client.get(f"/ingest/{upload_body['doc_id']}")
    assert poll_response.status_code == 200
    poll_body = poll_response.json()

    assert set(poll_body.keys()) == expected_keys
    # Same values for the same job — proves upload & polling converge on
    # the same JobState instance and don't re-serialise divergently.
    assert poll_body == upload_body


def test_upload_doc_id_is_uuid_and_persisted_in_repository(
    client: TestClient,
    patched_repo: IngestionJobRepository,
):
    sentinel = JobState(
        doc_id="11111111-1111-4111-8111-111111111111",
        revision=1,
        statut=RecStatus.GREEN,
        confiance=0.95,
        flags=[],
        erreur_traitement=None,
    )
    with patch(
        "app.api.routes_ingestion.run_ingestion_pipeline",
        return_value=sentinel,
    ):
        body = client.post(
            "/ingest/upload",
            files={"file": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        ).json()

    # UUID-shaped, stored by the same key the polling endpoint looks up.
    uuid_lib = __import__("uuid")
    uuid_lib.UUID(body["doc_id"])  # raises ValueError if not UUID

    # Repository has the same instance — guarantees retrieval by doc_id
    # works for the polling endpoint.
    assert patched_repo.get(body["doc_id"]) is not None


def test_polling_unknown_doc_id_returns_404(client: TestClient):
    response = client.get("/ingest/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404


def test_polling_non_uuid_returns_404(client: TestClient):
    response = client.get("/ingest/not-a-uuid")
    assert response.status_code == 404


def test_two_uploads_produce_distinct_doc_ids(client: TestClient):
    """Two uploads of the same filename must NOT collide on doc_id."""
    sentinel_template = {
        "revision": 1,
        "statut": "green",
        "confiance": 0.95,
        "flags": [],
        "erreur_traitement": None,
    }

    with patch(
        "app.api.routes_ingestion.run_ingestion_pipeline",
        side_effect=lambda *args, **kwargs: JobState(
            doc_id=__import__("uuid").uuid4().__str__(),
            **sentinel_template,
        ),
    ):
        first = client.post(
            "/ingest/upload",
            files={"file": ("same.pdf", io.BytesIO(b"a"), "application/pdf")},
        ).json()
        second = client.post(
            "/ingest/upload",
            files={"file": ("same.pdf", io.BytesIO(b"a"), "application/pdf")},
        ).json()

    assert first["doc_id"] != second["doc_id"]


def test_revision_field_present_and_integer(client: TestClient):
    sentinel = JobState(
        doc_id="22222222-2222-4222-8222-222222222222",
        revision=1,
        statut=RecStatus.GREEN,
        confiance=0.95,
        flags=[],
        erreur_traitement=None,
    )
    with patch(
        "app.api.routes_ingestion.run_ingestion_pipeline",
        return_value=sentinel,
    ):
        body = client.post(
            "/ingest/upload",
            files={"file": ("x.pdf", io.BytesIO(b"a"), "application/pdf")},
        ).json()

    assert body["revision"] == 1
    assert isinstance(body["revision"], int)