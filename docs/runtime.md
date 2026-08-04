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
| Demo (default) | `VLM_ENABLED=true\|false`, no broker wired  | Synchronous  | None — in-process |
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
| VLM (Ollama)  | Optional  | Optional   | `VLM_ENABLED=false` short-circuits the VLM path entirely.          |
| Redis         | Optional  | Required   | Demo mode never queries Redis.                                     |
| Postgres      | Optional  | Required   | Demo mode uses an in-memory repository.                            |
| Celery        | Optional  | Required   | Demo mode runs the pipeline in-process.                            |

**`VLM_ENABLED=false` semantics:** when the flag is false, the
`extract_fields()` orchestrator skips the VLM call entirely and
classifies low-confidence Docling results as AMBER (reviewable). The
readiness probe reports VLM as `disabled`, not `down`.

## Feature flags

| Flag                       | Default              | Effect when off / changed                                   |
| -------------------------- | -------------------- | ----------------------------------------------------------- |
| `VLM_ENABLED`              | `true`               | Skip VLM path; classify low-confidence Docling as AMBER.    |
| `DOCLING_CONFIDENCE_THRESHOLD` | `0.75`            | Below threshold = trigger VLM fallback.                      |
| `VLM_DEFAULT_CONFIDENCE`   | `0.6`                | Confidence assigned to VLM-extracted records.                |
| `OLLAMA_TIMEOUT_SECONDS`   | `120`                | Per-call HTTP timeout for Ollama.                            |
| `OLLAMA_HOST` (server bind) | n/a (env-controlled) | Bind address when starting `ollama serve`. Distinct from client-side `OLLAMA_BASE_URL`. |
| `OLLAMA_BASE_URL`          | `http://127.0.0.1:11434` | Client-side URL the pipeline POSTs to. **In WSL, must be the Windows host IP, not `127.0.0.1`.** |

## Endpoint dependency contracts

### `GET /health/live`

- **Hard deps:** FastAPI process alive.
- **Optional deps:** None.
- **Response:** Always 200 `{"status": "ok"}` unless the server is wedged.

### `GET /health/ready`

- **Hard deps (demo mode):** Docling importable, `DocumentConverter` usable.
- **Optional deps:** VLM, Redis, Postgres, Celery.
- **Response shape:**
  ```json
  {
    "status": "ok",
    "mode": "demo",
    "checks": {
      "docling": {"status": "up", "required": true},
      "vlm":     {"status": "up|down|disabled", "required": false, "url": "..."}
    },
    "degraded": true  // present only when an optional dep is down
  }
  ```
- **Codes:**
  - 200 with `status: "ok"` — all hard deps up. Optional deps may be down; if so, `degraded: true` is present.
  - 503 with `status: "down"` — a hard dep is missing. Don't upload.

### `GET /health` (legacy)

Returns the readiness payload. Kept for backward compatibility; new
code should prefer `/health/live` and `/health/ready`.

### `POST /ingest/upload`

- **Hard deps (demo mode):** FastAPI up, Docling importable, extraction
  + validation + anomaly code loaded.
- **Optional deps:** VLM. When unavailable, the pipeline degrades to
  Docling-only and the result is AMBER.
- **Not yet required:** Celery, Redis, Postgres.
- **Response:** A `JobState` with the six-field contract (`doc_id`,
  `revision`, `statut`, `confiance`, `flags`, `erreur_traitement`).

### `GET /ingest/{doc_id}`

- **Hard deps:** In-memory repository (always available in demo mode).
- **Optional deps:** None.
- **Codes:** 200 with the stored `JobState`; 404 if not found.

## Fallback policy — keep the best available extraction

The orchestrator implements a single rule: **a failed VLM fallback
must not overwrite a usable Docling result.** Concretely:

| Docling                       | VLM                          | Final       | Reviewer-visible flag(s)                |
| ----------------------------- | ---------------------------- | ----------- | --------------------------------------- |
| High confidence + complete     | Not called                   | GREEN       | (none)                                  |
| Low confidence + complete     | Disabled (`VLM_ENABLED=false`) | AMBER       | `vlm_disabled_in_env`, `docling_low_confidence_review` |
| Low confidence + complete     | Unreachable (transport)      | AMBER       | `vlm_unreachable`, `docling_low_confidence_review` |
| Low confidence + complete     | Returns no record            | AMBER       | `vlm_unreachable`, `docling_low_confidence_review` |
| Low confidence + complete     | Returns valid record         | AMBER/GREEN | `vlm_fallback`                          |
| Hard failure (exception/parse) | Disabled                    | RED         | `docling_parse_failed`                  |
| Hard failure                  | Unreachable                  | RED         | `docling_parse_failed`, `vlm_unreachable` |

AMBER means "usable record exists, but a human should look at it."
RED means "no usable record, nothing for a human to act on." RED is
stuck — neither VLM nor validation promotes a RED result upward.

## Canonical flag vocabulary

The orchestrator-level flag stream is **additive**: each flag is a
small string the reviewer can interpret independently. Multiple flags
can co-exist on the same record; never collapse them into a single
compound name.

| Flag                              | Meaning                                                              | Action for reviewer                       |
| --------------------------------- | -------------------------------------------------------------------- | ----------------------------------------- |
| `vlm_unreachable`                 | VLM expected but transport failed (network/timeout/host unreachable). | Investigate connectivity (host IP, firewall, `ollama serve`). |
| `vlm_disabled_in_env`             | VLM intentionally disabled by config (`VLM_ENABLED=false`).          | Accept the Docling result; focus on completeness. |
| `vlm_fallback`                    | VLM rescue path was used successfully.                               | The read came from the less-trusted path; inspect carefully. |
| `docling_low_confidence_review`   | Docling produced a usable record below the confidence threshold.     | Inspect and decide; the read is shaky.    |
| `low_confidence`                  | Generic low-confidence marker. Kept for backward compatibility.     | Treat as a confidence signal.             |
| `missing_fields:<f1,f2,...>`      | Required fields absent after extraction.                             | Add the missing fields to the source doc; otherwise flag the record. |

Flag scoping is **record-level only**. Job-level context is surfaced by
`status_extraction` and `JobState`, not by duplicating flags across
records.

## Networking assumptions

The WSL/Windows-host topology trips up newcomers. The two pieces:

- **`OLLAMA_HOST`** is the bind address for the Ollama server (passed
  to `ollama serve` as `OLLAMA_HOST=0.0.0.0` on the Windows host so it
  listens on every interface).
- **`OLLAMA_BASE_URL`** is the client-side URL the pipeline uses to
  reach Ollama. **In WSL, this must be the Windows host IP** (e.g.
  `http://172.20.x.x:11434`), **never `127.0.0.1`**. Loopback inside
  WSL points to WSL's own loopback, not the Windows host.

Other networking requirements:

- Windows firewall must allow inbound TCP on port `11434` from the WSL
  virtual NIC.
- WSL2's NAT means `127.0.0.1` on Windows is not reachable from WSL
  unless mirrored mode is enabled — and even then, prefer the host IP
  for clarity.

## Repo map — where each contract lives

| Concern                        | File                            |
| ------------------------------ | ------------------------------- |
| Mode flag (`VLM_ENABLED`)      | `app/core/config.py`            |
| Fallback orchestration         | `app/ingestion/tasks.py`       |
| Docling path                   | `app/ingestion/docling_path.py` |
| VLM path                       | `app/ingestion/vlm_path.py`     |
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