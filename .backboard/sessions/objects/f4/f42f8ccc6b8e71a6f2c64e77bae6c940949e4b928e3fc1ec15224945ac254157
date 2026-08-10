# Spec: Make the HR Anomaly Pipeline Runtime-Safe Under WSL/Local Constraints

## Problem Statement

The HR anomaly pipeline has hidden runtime assumptions that cause silent failures and confusing behavior, especially under the WSL + Windows host topology that this machine uses. Three specific problems:

1. **No explicit runtime modes.** The codebase describes a full Celery + Redis + Postgres stack in documentation, but the actual running code is a synchronous, in-memory demo pipeline. There is no feature flag or mode switch — the code just behaves differently depending on what dependencies happen to be installed.

2. **VLM fallback destroys usable Docling results.** When Docling produces a usable record at low confidence and the VLM fallback is unreachable, the pipeline classifies the result as RED (hard failure) instead of AMBER (reviewable). The fallback error overwrites the upstream Docling success, rejecting records that a human reviewer could still act on.

3. **No dependency visibility.** The `/health` endpoint always returns `{"status": "ok"}` regardless of whether Docling, Ollama, Redis, or Postgres are reachable. There is no readiness probe, no degraded-but-usable signal, and no way for an operator to know which dependencies are actually available before uploading a document.

These problems are compounded by WSL networking: `ollama_base_url` defaults to `http://127.0.0.1:11434`, which points to WSL's own loopback, not the Windows host where Ollama runs. The distinction between `OLLAMA_HOST` (server bind) and `ollama_base_url` (client target) is not documented or enforced.

## Solution

Make every runtime assumption explicit, testable, and visible:

1. **Define three runtime modes** with a feature flag (`VLM_ENABLED`) and a mode matrix that maps each mode to its required and optional dependencies.

2. **Fix the fallback policy** so that a usable Docling result is never overwritten by a failed VLM fallback. Low-confidence Docling results become AMBER (reviewable) instead of RED (rejected) when the VLM is unavailable.

3. **Split health into liveness and readiness** probes (`/health/live` and `/health/ready`) where readiness is mode-aware and fails only on hard dependencies of the active mode.

4. **Create `docs/runtime.md`** as the canonical operator-facing document for runtime contracts, networking assumptions, and dependency expectations.

## User Stories

1. As a developer running the pipeline inside WSL, I want to set `VLM_ENABLED=false` and have the pipeline work with Docling only, so that I can use the pipeline without needing Ollama reachable from WSL.

2. As a developer running the pipeline inside WSL, I want `ollama_base_url` to point to the Windows host IP (not `127.0.0.1`) when VLM is enabled, so that the client can actually reach the Ollama server.

3. As a developer, I want `OLLAMA_HOST` (server bind) and `ollama_base_url` (client target) to be documented as separate config pieces, so that I don't confuse server-side and client-side networking.

4. As an operator, I want `POST /ingest/upload` to return AMBER (not RED) when Docling produces a usable record but the VLM fallback is unavailable, so that the record stays in the review queue instead of being rejected.

5. As an operator, I want the pipeline to preserve the best available extraction when a fallback fails, so that a successful Docling result is never overwritten by a failed VLM rescue attempt.

6. As an operator, I want to see canonical flags (`vlm_unreachable`, `vlm_disabled_in_env`, `docling_low_confidence_review`) on records, so that I know whether to investigate connectivity or focus on review.

7. As an operator, I want `/health/live` to tell me the FastAPI process is alive, so that I know the server is running.

8. As an operator, I want `/health/ready` to tell me whether the pipeline can accept a document right now, so that I know if it is safe to upload.

9. As an operator, I want `/health/ready` to return 200 with degraded detail when optional dependencies (VLM, Redis) are unavailable but hard dependencies (Docling) are present, so that I can still use the pipeline in demo mode.

10. As an operator, I want `/health/ready` to return 503 when a hard dependency (Docling) is missing, so that I know the pipeline cannot process documents at all.

11. As a developer, I want the runtime mode matrix to be documented in a single file (`docs/runtime.md`), so that I can look up what each mode requires without reading the whole codebase.

12. As a developer, I want each endpoint's dependency contract documented, so that I know what is required vs optional before I call it.

13. As a developer, I want code-local assumption notes only where assumptions directly affect behavior (e.g., WSL-sensitive config defaults), so that the primary source of truth is `docs/runtime.md` and not scattered across module docstrings.

14. As a reviewer, I want flag combinations to be additive (multiple simple flags, not compound names), so that I can understand each flag independently and compose them mentally.

15. As a reviewer, I want `vlm_unreachable` to signal a transient network problem (check Ollama, firewall, host IP), so that I take operational action.

16. As a reviewer, I want `vlm_disabled_in_env` to signal an intentional design choice (VLM is off by policy), so that I accept the Docling result and focus on completeness.

17. As a reviewer, I want `docling_low_confidence_review` to signal that a usable record needs human judgment, so that I know to inspect and decide.

18. As a CI/CD operator, I want the readiness probe to be testable against `docs/runtime.md`, so that the documented contract and the actual behavior stay in sync.

19. As a future maintainer, I want the distinction between demo mode (synchronous, in-memory) and full-stack mode (Celery + Redis + Postgres) to be explicit, so that I don't assume Celery is running when it isn't.

20. As a future maintainer, I want `docs/runtime.md` to be updated whenever an endpoint contract or dependency assumption changes, so that the document stays authoritative.

## Implementation Decisions

### Runtime Modes and Feature Flags

Three runtime modes are officially supported:

- **Docling-only (demo)**: `VLM_ENABLED=false`. No VLM calls. No Redis, Postgres, or Celery required. Endpoints work synchronously with in-memory repo.
- **Full-stack (planned)**: `VLM_ENABLED` configurable. Redis + Postgres + Celery required. Endpoints enqueue Celery tasks.
- **Full-stack + VLM**: Full-stack with Ollama/vLLM reachable from WSL via Windows host IP.

The `VLM_ENABLED` feature flag controls whether the VLM fallback path is attempted at all. When `false`, `extract_fields()` in `tasks.py` skips the VLM call entirely and classifies low-confidence Docling results as AMBER.

### Endpoint Dependency Contracts

`POST /ingest/upload` (demo mode):
- Hard deps: FastAPI up, Docling importable, extraction + validation + anomaly code loaded.
- Optional deps: VLM (Ollama). When unavailable, pipeline degrades to Docling-only with AMBER status.
- Not yet required: Celery, Redis, Postgres.

`GET /ingest/{doc_id}`:
- Hard deps: In-memory repo (always available in demo mode).
- Optional deps: None.

`GET /health/live`:
- Hard deps: FastAPI process alive.
- Always returns 200 unless the process is crashing.

`GET /health/ready`:
- Hard deps (demo mode): Docling importable, `DocumentConverter` usable.
- Optional deps: VLM, Redis, Postgres, Celery.
- Returns 503 only when a hard dep is missing. Returns 200 with degraded detail when optional deps are down.

### Health and Readiness Semantics

- `/health/live` — process-only liveness probe. Always 200 unless the server is wedged.
- `/health/ready` — mode-aware readiness probe. Fails only on hard dependencies of the active runtime mode.
- Demo mode hard dep: Docling importable and `DocumentConverter` available.
- Demo mode soft deps: VLM unreachable = 200 with degraded detail, not 503.
- Empty in-memory repo = 200 (no jobs yet is application state, not a dependency failure).
- The health endpoint implements the contract defined in `docs/runtime.md`.

### Fallback Policy (No Live VLM)

Classification rule:
- RED — no usable record exists, or required extraction truly failed.
- AMBER — a usable record exists but confidence/completeness is insufficient for auto-clearance.
- GREEN — record is usable and passes the confidence/completeness policy without escalation.

Key principle: "Keep the best available extraction." A failed VLM fallback must not overwrite a usable Docling result. Docling success + low confidence + VLM unavailable = AMBER, not RED.

Canonical flag vocabulary (additive, not compound):
- `vlm_unreachable` — VLM expected but transport failed. Reviewer should investigate connectivity.
- `vlm_disabled_in_env` — VLM intentionally disabled by config. Reviewer should accept Docling result.
- `vlm_fallback` — VLM rescue path was used successfully.
- `docling_low_confidence_review` — Docling usable but below threshold, human review required.
- `missing_fields:<field1,field2>` — required fields absent after extraction.

Flag scoping: record-level only. Job-level context is surfaced by `status_extraction` and `JobState`, not by duplicating flags across records.

### Assumption Documentation

- `docs/runtime.md` — canonical runtime contracts: mode matrix, endpoint dependency table, networking, hard/optional dependency index.
- `docs/architecture.md` — target structure and major system design, not live operational assumptions.
- `AGENTS.md` — contributor/agent guidance, coding rules, security boundaries, pointer to runtime docs.
- `CONTEXT.md` — glossary and domain decisions, not live config defaults.
- Code-local notes — short comments only where assumptions directly affect behavior (e.g., WSL-sensitive config defaults, fallback preservation logic).
- Arrow direction: runtime doc defines the contract; health endpoints and route code reference and implement it.
- Governance: a small ADR records that runtime assumptions are canonically in `docs/runtime.md`; architecture rationale lives in ADRs; code comments only capture local implementation constraints.

### Networking Assumptions

- `OLLAMA_HOST` (server bind) and `ollama_base_url` (client target) are separate config pieces.
- In WSL, `ollama_base_url` must be the Windows host IP (e.g., `http://172.x.x.x:11434`), never `127.0.0.1`.
- Windows firewall must allow inbound TCP on port 11434 from the WSL virtual NIC.
- `VLM_ENABLED=false` disables the VLM path entirely; `ollama_base_url` is ignored in this mode.

### Seams

The highest seam to test against is `app/main.py` (app factory), which controls routing and lifespan. The next highest is `app/core/config.py` (config seam), which controls all dependency flags and URLs. The extraction orchestration seam is `app/ingestion/tasks.py` (`extract_fields()` and `validate_record()`).

Testing seams in priority order:
1. `app/main.py` — for health/live and health/ready endpoint routing.
2. `app/core/config.py` — for `VLM_ENABLED`, `ollama_base_url`, and mode-dependent config.
3. `app/ingestion/tasks.py` — for fallback policy (AMBER vs RED when VLM unavailable).
4. `app/ingestion/vlm_path.py` — for VLM unreachable handling.

## Testing Decisions

### What Makes a Good Test

Tests should verify external behavior (HTTP status codes, response bodies, flag values, status classifications) not implementation details (which function was called, internal state). Tests should cover:
- Each runtime mode's expected behavior for each endpoint.
- Each flag combination's expected status classification.
- Health/readiness probe responses for each dependency state.
- The "keep the best available extraction" principle (Docling success preserved when VLM fails).

### Modules to Test

- `app/main.py` — health/live and health/ready endpoints.
- `app/core/config.py` — `VLM_ENABLED` flag parsing, `ollama_base_url` defaults.
- `app/ingestion/tasks.py` — `extract_fields()` fallback policy, `_determine_extraction_status()`, `validate_record()`.
- `app/ingestion/vlm_path.py` — `extract_with_vlm()` unreachable handling.
- `app/ingestion/docling_path.py` — `extract_from_docling()` low-confidence handling.

### Prior Art

Existing tests in `tests/ingestion/test_tasks.py` and `tests/ingestion/test_vlm_path.py` cover the current extraction and VLM paths. New tests should extend these with:
- VLM-disabled mode scenarios.
- VLM-unreachable with Docling success scenarios (AMBER, not RED).
- Health/readiness probe scenarios for each dependency state.
- Flag combination scenarios for the canonical vocabulary.

## Out of Scope

- Celery/Redis/Postgres wiring (planned for full-stack mode, not in this spec).
- Multi-tenant auth / RBAC.
- Cloud deployment (Kubernetes, Docker Swarm, etc.).
- Any integration with non-local model providers (OpenAI, Gemini, Anthropic).
- Full Streamlit dashboard implementation.
- ADR creation for individual decisions (a single governance ADR for assumption documentation is sufficient).

## Further Notes

- The `docs/runtime.md` file should be created as part of this work and kept in sync with code changes via PR review.
- The `VLM_ENABLED` feature flag should be added to `Settings` in `app/core/config.py` with a default of `true` for backward compatibility, but the fallback policy change (AMBER instead of RED for Docling success + VLM unavailable) should apply regardless of the flag value — it is a policy decision, not a feature toggle.
- The `docs/runtime.md` should be referenced from `AGENTS.md` as the canonical runtime assumptions document, replacing the scattered runtime truth currently in `AGENTS.md`.
- The `README.md` quick-start section should be updated to reflect the Docling-only demo mode as the default path for new users, with full-stack setup as an optional follow-up.
- All 5 grilling session decisions (runtime topologies, endpoint contracts, health semantics, fallback policy, assumption documentation) are captured in this spec and in `CONTEXT.md`.