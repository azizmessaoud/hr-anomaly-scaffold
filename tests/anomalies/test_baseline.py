"""Tests for the in-memory cohort baseline store."""

from __future__ import annotations

from app.anomalies.baseline import (
    CohortBaselineStore,
    get_default_baseline_store,
    reset_default_baseline_store,
)


class TestCohortBaselineStore:
    def test_add_and_values(self):
        store = CohortBaselineStore()
        store.add(("IT",), 4000.0)
        store.add(("IT",), 5000.0)
        assert store.values(("IT",)) == [4000.0, 5000.0]

    def test_values_returns_copy(self):
        store = CohortBaselineStore()
        store.add(("IT",), 4000.0)
        vals = store.values(("IT",))
        vals.append(9999.0)
        assert store.values(("IT",)) == [4000.0]

    def test_size(self):
        store = CohortBaselineStore()
        assert store.size(("IT",)) == 0
        store.add(("IT",), 4000.0)
        assert store.size(("IT",)) == 1

    def test_is_ready(self):
        store = CohortBaselineStore()
        assert not store.is_ready(("IT",), 3)
        store.add(("IT",), 4000.0)
        store.add(("IT",), 4100.0)
        assert not store.is_ready(("IT",), 3)
        store.add(("IT",), 4200.0)
        assert store.is_ready(("IT",), 3)

    def test_extend(self):
        store = CohortBaselineStore()
        store.extend(("IT",), [1.0, 2.0, 3.0])
        assert store.values(("IT",)) == [1.0, 2.0, 3.0]

    def test_clear(self):
        store = CohortBaselineStore()
        store.add(("IT",), 4000.0)
        store.clear()
        assert store.size(("IT",)) == 0

    def test_cohorts(self):
        store = CohortBaselineStore()
        store.add(("IT",), 4000.0)
        store.add(("HR",), 3000.0)
        assert set(store.cohorts()) == {("IT",), ("HR",)}

    def test_unknown_cohort_returns_empty(self):
        store = CohortBaselineStore()
        assert store.values(("NONEXISTENT",)) == []


class TestDefaultStore:
    def test_get_returns_same_instance(self):
        s1 = reset_default_baseline_store()
        s2 = get_default_baseline_store()
        assert s1 is s2

    def test_reset_creates_fresh(self):
        s1 = get_default_baseline_store()
        s1.add(("IT",), 4000.0)
        s2 = reset_default_baseline_store()
        assert s2.size(("IT",)) == 0
