from __future__ import annotations

import uuid

# Surrogate identity — never derived from filename, never user-controllable.
# Re-ingestion of the same logical document produces a new doc_id; the
# ``revision`` field is the only thing that increments within a doc_id.
INITIAL_REVISION = 1


def generate_doc_id() -> str:
    """Return a fresh surrogate UUID for a new ingestion.

    Never derived from filename, hash of file contents, or any user-supplied
    value — so a retry, a re-upload of the same logical document, and an
    upload of a different document with the same filename are all
    distinguishable, and the SIRH idempotency key stays stable across the
    pipeline.
    """
    return str(uuid.uuid4())


def is_valid_doc_id(value: object) -> bool:
    """Accept a UUID-shaped string. Cheap; does not normalise."""
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True