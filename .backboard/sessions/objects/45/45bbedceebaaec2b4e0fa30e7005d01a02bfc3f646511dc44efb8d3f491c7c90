"""In-memory cohort baseline store.

Mirrors :class:`app.ingestion.repository.IngestionJobRepository` —
demo-mode seam intended to be swapped for Postgres in full-stack mode.

The store holds, per cohort key, the list of ``salaire_brut`` values
from validated records. Only validated records contribute (the
orchestrator appends a record after ``validate_record`` succeeds), so a
malformed or partial extraction can never pollute the baseline.

The store is append-only by design. A future "approved only" baseline
can be added behind a new method without breaking existing callers —
this matters because :mod:`app.ingestion.job_state` does not yet
implement an approval workflow, so the only defensible choice under
the current contract is "validated records contribute."
"""

from __future__ import annotations

import threading
from typing import Iterable


class CohortBaselineStore:
    """Append-only, thread-safe in-memory store of cohort sample values.

    Thread-safety: ingestion is currently synchronous (demo mode), so a
    lock is overkill today. The lock is included anyway because the
    orchestrator's regression tests pass it through ``monkeypatch`` and
    run under ``pytest-xdist`` in CI — a no-op contention point in the
    single-process dev case is cheaper than debugging a flaky test.
    """

    def __init__(self) -> None:
        self._values: dict[tuple[str, ...], list[float]] = {}
        self._lock = threading.Lock()

    # -- mutation ---------------------------------------------------------
    def add(self, cohort: tuple[str, ...], value: float) -> None:
        """Append ``value`` to ``cohort``'s sample list."""
        with self._lock:
            self._values.setdefault(cohort, []).append(float(value))

    def extend(self, cohort: tuple[str, ...], values: Iterable[float]) -> None:
        with self._lock:
            bucket = self._values.setdefault(cohort, [])
            for v in values:
                bucket.append(float(v))

    def clear(self) -> None:
        """Drop every cohort. Intended for tests."""
        with self._lock:
            self._values.clear()

    # -- reads ------------------------------------------------------------
    def values(self, cohort: tuple[str, ...]) -> list[float]:
        """Return a copy of the cohort's sample list. Never the live list."""
        with self._lock:
            return list(self._values.get(cohort, []))

    def size(self, cohort: tuple[str, ...]) -> int:
        with self._lock:
            return len(self._values.get(cohort, []))

    def is_ready(self, cohort: tuple[str, ...], min_samples: int) -> bool:
        """True iff ``cohort`` has at least ``min_samples`` samples."""
        return self.size(cohort) >= min_samples

    def cohorts(self) -> list[tuple[str, ...]]:
        """Return a copy of the cohort keys currently in the store."""
        with self._lock:
            return list(self._values.keys())


# ---------------------------------------------------------------------------
# Module-level default instance, mirroring IngestionJobRepository's pattern.
# ---------------------------------------------------------------------------

_default_store: CohortBaselineStore | None = None


def get_default_baseline_store() -> CohortBaselineStore:
    """Return the process-wide default cohort baseline store.

    The first call constructs it; subsequent calls return the same
    instance. Tests should call :func:`reset_default_baseline_store`
    between cases (or :meth:`CohortBaselineStore.clear` on a
    ``monkeypatch``-injected instance).
    """
    global _default_store
    if _default_store is None:
        _default_store = CohortBaselineStore()
    return _default_store


def reset_default_baseline_store() -> CohortBaselineStore:
    """Drop the default store and return a fresh empty one.

    Used by tests; never call this from production code.
    """
    global _default_store
    _default_store = CohortBaselineStore()
    return _default_store
