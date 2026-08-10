# AGENTS.md — HR Anomaly Scaffold

## Project goal
A local, secure AI pipeline for detecting anomalies in HR files before integration.

## Canonical documents
- `docs/architecture.md` = source of truth for architecture
- `docs/runtime.md` = canonical runtime contracts (modes, endpoints, dependencies, networking). **Start here for any question about "is X required or optional?" or "what happens when Y is down?"**
- `CONTEXT.md` = glossary and current domain decisions

## Runtime truth
- Development happens from Windows PowerShell, but the backend runs inside WSL.
- The Python environment is inside WSL at `.venv`.
- Standard backend startup:
  - `wsl`
  - `source .venv/bin/activate`
  - `python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`
- For runtime contracts, dependency expectations, networking assumptions, and the
  full mode matrix, see **`docs/runtime.md`**. That document is authoritative —
  this file only carries the local dev shell notes.

## Local model setup
- No local LLM models are used in the current pipeline.
- Extraction relies on Docling (structured documents) and RapidOCR (scanned documents).
- Do not add LLM dependencies without updating AGENTS.md and architecture.md.

## Current code seams
- `app/main.py` — app factory seam
- `app/api/health.py` — liveness (`/health/live`) and readiness (`/health/ready`) probes. Contract is in `docs/runtime.md`.
- `app/core/config.py` — config seam (mode-dependent settings)
- `app/ingestion/tasks.py` — orchestration seam for ingestion (fallback policy lives here)
- `app/ingestion/extraction_result.py` — canonical flag vocabulary (`flag_rapidocr_unreachable`, `flag_rapidocr_disabled_in_env`, etc.)
- `app/anomalies/orchestrator.py` — anomaly detection seam (`detect_anomalies: StageResult -> StageResult`)
- `app/anomalies/baseline.py` — cohort baseline store seam (in-memory adapter, swap for Postgres later)
- `app/pipeline/completeness.py` — shared payroll completeness rule (5-field)
- `app/pipeline/status_composition.py` — record status composition seam

## Pipeline flow

```
ingest_document → extract_fields → validate_record → detect_anomalies → stage_to_job_state
```

Each step is a `StageResult -> StageResult` seam. The orchestrator (`tasks.py`) threads the record through these steps. Anomaly detection (`detect_anomalies`) is advisory only — it adds flags but never mutates `RecStatus`.

## Debugging policy
- Reproduce first.
- Patch the narrowest seam.
- Add a regression test.
- Prefer diagnosis over refactors.
- Do not expand scope without saying so.

## Security constraints
- Never send real HR data to cloud models or cloud OCR.
- Never bypass human review.
- Never commit real HR documents.