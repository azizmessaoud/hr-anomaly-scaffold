from __future__ import annotations

import uuid

from app.ingestion.doc_id import (
    INITIAL_REVISION,
    generate_doc_id,
    is_valid_doc_id,
)


def test_generate_doc_id_returns_uuid_string():
    doc_id = generate_doc_id()
    assert isinstance(doc_id, str)
    # Must parse as a UUID — guards against future regressions that
    # accidentally hash filenames or reuse a counter.
    parsed = uuid.UUID(doc_id)
    assert str(parsed) == doc_id


def test_generate_doc_id_differs_across_calls():
    a = generate_doc_id()
    b = generate_doc_id()
    assert a != b


def test_is_valid_doc_id_accepts_uuid_strings():
    assert is_valid_doc_id("550e8400-e29b-41d4-a716-446655440000") is True
    assert is_valid_doc_id(generate_doc_id()) is True


def test_is_valid_doc_id_rejects_non_uuid_strings():
    assert is_valid_doc_id("") is False
    assert is_valid_doc_id("not-a-uuid") is False
    assert is_valid_doc_id("upload_123.pdf") is False
    assert is_valid_doc_id("doc-id-1") is False


def test_is_valid_doc_id_rejects_non_strings():
    assert is_valid_doc_id(None) is False
    assert is_valid_doc_id(123) is False
    assert is_valid_doc_id([]) is False


def test_initial_revision_is_one():
    assert INITIAL_REVISION == 1