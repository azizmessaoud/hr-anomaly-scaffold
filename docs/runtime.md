# Runtime Contract — HR Anomaly Pipeline

This document is the **canonical** reference for runtime assumptions,
endpoint contracts, and dependency expectations. Every PR that changes
an endpoint contract, a hard/optional dependency boundary, or a runtime
mode assumption must update this file in the same PR.

If something here contradicts `app/**` behavior, **the code is the
source of truth until this doc is updated** — open a follow-up, don't
silently patch one side.

## Topology overview

Two runtime modes are officially supported:

| Mode           | Trigger                                     | Endpoints    | Worker            |
| -------------- | ------------------------------------------- | ------------ | ----------------- |
| Demo (default) | No broker wired                             | Synchronous  | None — in-process |
| Full-stack     | Celery + Redis + Postgres wired (planned)   | Async        | Celery worker     |

Demo mode is the default path for new users and for the WSL/Windows
host dev setup. Full-stack mode is planned but not yet implemented.

## Runtime mode matrix

The matrix below shows what each mode requires and what each mode
tolerates. "Required" means the readiness probe (`/health/ready`)
returns 503 when the dependency is missing. "Optional" means missing
or down is reported in the response body but does not flip status to
unready.

| Dependency    | Demo mode | Full-stack | Notes                                                              |
| ------------- | --------- | ---------- | ------------------------------------------------------------------ |
| FastAPI       | Required  | Required   | The process must be up; otherwise the probe itself fails.          |
| Docling       | Required  | Required   | Layer 1 ingestion/extraction; without it, the pipeline can't run.  |
| RapidOCR      | Optional  | Optional   | `RAPIDOCR_ENABLED=false` short-circuits the RapidOCR path entirely.|
| Redis         | Optional  | Required   | Demo mode never queries Redis.                                     |
| Postgres      | Optional  | Required   | Demo mode uses an in-memory repository.                            |
| Celery        | Optional  | Required   | Demo mode runs the pipeline in-process.                            |

**`RAPIDOCR_ENABLED=false` semantics:** when the flag is false, the
`extract_fields()` orchestrator skips the RapidOCR call entirely and
classifies low-confidence Docling results as AMBER (reviewable). The
readiness probe reports RapidOCR as `disabled`, not `down`.

## Feature flags

| Flag                       | Default              | Effect when off / changed                                   |
| -------------------------- | -------------------- | ----------------------------------------------------------- |
| `RAPIDOCR_ENABLED`         | `true`               | Skip RapidOCR path; classify low-confidence Docling as AMBER.|
| `DOCLING_CONFIDENCE_THRESHOLD` | `0.75`            | Below threshold = trigger RapidOCR fallback.                 |
| `RAPIDOCR_DEFAULT_CONFIDENCE` | `0.6`              | Confidence assigned to RapidOCR-extracted records.           |

## Endpoint dependency contracts

### `GET /health/live`

- **Hard deps:** FastAPI process alive.
- **Optional deps:** None.
- **Response:** Always 200 with `status: "ok"` and the application name unless the server is wedged.

### `GET /health/ready`

- **Hard deps (demo mode):** Docling importable, `DocumentConverter` usable.
- **Optional deps:** RapidOCR, Redis, Postgres, Celery.
- **Response shape:**
  ```json
  {
    "status": "ready",
    "app": "hr-anomaly-pipeline",
    "mode": "demo_with_rapidocr",
    "checks": {
      "docling": {"status": "up", "required": true},
      "rapidocr": {"status": "up|down|disabled", "required": false}
    },
    "degraded": true  // present only when an optional dep is down
  }
  ```
- **Codes:**
  - 200 with `status: "ready"` — all hard and optional deps are up.
  - 200 with `status: "degraded"` — hard deps are up but an optional dependency is down.
  - 503 with `status: "not_ready"` — a hard dep is missing. Don't upload.

### `GET /health` (legacy)

Returns the readiness payload. Kept for backward compatibility; new
code should prefer `/health/live` and `/health/ready`.

### `POST /ingest/upload`

- **Hard deps (demo mode):** FastAPI up, Docling importable, extraction
  + validation + anomaly code loaded.
- **Optional deps:** RapidOCR. When unavailable, the pipeline degrades to
  Docling-only and the result is AMBER.
- **Not yet required:** Celery, Redis, Postgres.
- **Response:** A `JobState` with the six-field contract (`doc_id`,
  `revision`, `statut`, `confiance`, `flags`, `erreur_traitement`).

### `GET /ingest/{doc_id}`

- **Hard deps:** In-memory repository (always available in demo mode).
- **Optional deps:** None.
- **Codes:** 200 with the stored `JobState`; 404 if not found.

### `GET /ingest/{doc_id}/report`

- Returns the privacy-conscious `AnalysisReport` for the document.
- The report contains summary counters, grouped anomaly counts,
  recommendations, and a bounded list of explainable anomaly details.
- Source HR records are not returned by this endpoint.
- Returns 404 when the document/job is unknown.

### Upload pre-flight validation

The synchronous demo path validates extension, non-empty content, configured
maximum size, and the PDF/image container before OCR. The supported current
extensions are PDF and common image formats. CSV and Excel are not part of the
current runtime contract; they require a dedicated tabular schema pipeline.

## Fallback policy — keep the best available extraction

The orchestrator implements a single rule: **a failed RapidOCR fallback
must not overwrite a usable Docling result.** Concretely:

| Docling                       | RapidOCR                     | Final       | Reviewer-visible flag(s)                |
| ----------------------------- | ---------------------------- | ----------- | --------------------------------------- |
| High confidence + complete     | Not called                   | GREEN       | (none)                                  |
| Low confidence + complete     | Disabled (`RAPIDOCR_ENABLED=false`) | AMBER       | `rapidocr_disabled_in_env`, `docling_low_confidence_review` |
| Low confidence + complete     | Unreachable (engine)         | AMBER       | `rapidocr_unreachable`, `docling_low_confidence_review` |
| Low confidence + complete     | Returns no record            | AMBER       | `rapidocr_unreachable`, `docling_low_confidence_review` |
| Low confidence + complete     | Returns valid record         | AMBER/GREEN | `rapidocr_fallback`                     |
| Hard failure (exception/parse) | Disabled                    | RED         | `docling_parse_failed`                  |
| Hard failure                  | Unreachable                  | RED         | `docling_parse_failed`, `rapidocr_unreachable` |

AMBER means "usable record exists, but a human should look at it."
RED means "no usable record, nothing for a human to act on." RED is
stuck — neither RapidOCR nor validation promotes a RED result upward.

## Canonical flag vocabulary

The orchestrator-level flag stream is **additive**: each flag is a
small string the reviewer can interpret independently. Multiple flags
can co-exist on the same record; never collapse them into a single
compound name.

| Flag                              | Meaning                                                              | Action for reviewer                       |
| --------------------------------- | -------------------------------------------------------------------- | ----------------------------------------- |
| `rapidocr_unreachable`            | RapidOCR expected but engine not available.                          | Investigate onnxruntime installation.     |
| `rapidocr_disabled_in_env`        | RapidOCR intentionally disabled by config (`RAPIDOCR_ENABLED=false`).| Accept the Docling result; focus on completeness. |
| `rapidocr_fallback`               | RapidOCR rescue path was used successfully.                          | The read came from the less-trusted path; inspect carefully. |
| `docling_low_confidence_review`   | Docling produced a usable record below the confidence threshold.     | Inspect and decide; the read is shaky.    |
| `low_confidence`                  | Generic low-confidence marker. Kept for backward compatibility.     | Treat as a confidence signal.             |
| `missing_fields:<f1,f2,...>`      | Required fields absent after extraction.                             | Add the missing fields to the source doc; otherwise flag the record. |

Flag scoping is **record-level only**. Job-level context is surfaced by
`status_extraction` and `JobState`, not by duplicating flags across
records.

## Networking assumptions

- No special networking requirements for demo mode; all processing is local.
- In full-stack mode, Redis and Postgres must be reachable from the API server and Celery workers.

## Repo map — where each contract lives

| Concern                        | File                            |
| ------------------------------ | ------------------------------- |
| Feature flags                  | `app/core/config.py`            |
| Fallback orchestration         | `app/ingestion/tasks.py`       |
| Docling path                   | `app/ingestion/docling_path.py` |
| RapidOCR path                  | `app/ingestion/rapidocr_path.py`|
| Extraction result boundary     | `app/ingestion/extraction_result.py` |
| Status composition             | `app/pipeline/status_composition.py` |
| Shared payroll completeness    | `app/pipeline/completeness.py`  |
| Health endpoints               | `app/api/health.py`             |
| FastAPI app factory            | `app/main.py`                   |

## What this document is NOT

- **Not** an architecture overview (that's `docs/architecture.md`).
- **Not** a glossary (that's `CONTEXT.md`).
- **Not** a contributor guide (that's `AGENTS.md`).

It is specifically the runtime contracts document: if you're asking
"is X required or optional?" or "what happens when Y is down?", this
is the file.

## Updating this doc

Any change to an endpoint contract, a hard/optional dependency
boundary, or a runtime mode assumption must update this file in the
same PR. The PR review should explicitly call out the doc update
("updates `docs/runtime.md`") so reviewers can confirm the contract
and the implementation stay in sync.