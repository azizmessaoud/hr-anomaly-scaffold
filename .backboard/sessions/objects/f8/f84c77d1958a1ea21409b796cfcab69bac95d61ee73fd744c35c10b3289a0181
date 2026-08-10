"""Cohort key extraction.

The architecture doc (§2 Layer 4) recommends grouping by
``departemenent / grade / site`` to avoid false positives from
legitimate inter-team differences. The current ``HRRecord`` schema
carries ``departement`` only — ``grade`` and ``site`` are not yet
modelled. The cohort key is therefore ``(departement,)`` for now.

A future maintainer expanding the grouping should:

- Add the field to ``HRRecord`` (requires a schema discussion per
  ``AGENTS.md``, not a silent edit).
- Extend :func:`cohort_key` to return ``(departement, grade)`` etc.
- Re-evaluate ``MIN_COHORT_SIZE`` — expanding the grouping shrinks
  per-cohort sample sizes and may push the minimum upward.
"""

from __future__ import annotations

from typing import Optional

from app.ingestion.schemas import HRRecord


def cohort_key(record: HRRecord) -> Optional[tuple[str, ...]]:
    """Return the cohort key for ``record``, or ``None`` if it cannot
    participate in any cohort (missing ``departement``).

    Records with no ``departement`` are skipped by the orchestrator:
    they cannot contribute to a salary distribution and cannot be
    scored against one. This is not a failure — it is the correct
    behaviour for an HR record with no team affiliation.
    """
    departement = record.departement
    if departement is None or departement == "":
        return None
    return (departement,)
