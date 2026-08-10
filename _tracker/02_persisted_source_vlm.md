## Question

Is there any persisted data (DB rows, cached job state, fixtures) that stores `source="vlm"` as a literal string that would break on rename, or is this purely an in-memory/test-time value with no migration concern? (Given AD-009/pgvector is out of MVP scope and the pipeline looks stateless per-job today, this is likely a non-issue — confirm and close quickly rather than let it linger as unticketed doubt.)

## Answer

No persisted data stores `source="vlm"` as a literal string. The `source` field in `ExtractionResult` is purely in-memory and test-time. The `JobState` model does not persist `source` — it only carries `flags` (string names) and `erreur_traitement` (error codes). The test fixtures in `test_vlm_path.py` use `source="vlm"` but that file will be deleted entirely as part of this refactor. No migration is needed.

**Resolution**: 2026-08-08. Confirmed no migration concern. Ticket closed.
