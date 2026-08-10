# System Record — HR Anomaly Detection Pipeline

## What This System Is

A self-hosted, 100% open-source pipeline that intercepts HR documents (PDF and image uploads), extracts structured personal and employment data from them, validates the extracted records through deterministic rules and statistical anomaly detection, and only releases approved records toward the SIRH/payroll system after a human reviewer has signed off.

No data leaves the controlled infrastructure. No cloud LLM is called on real documents.

## What This System Does

### 1. Ingestion (Layer 1)

A document arrives via upload (PDF or image). The pipeline routes it through a tiered extraction strategy:

- **Docling** (primary) — parses the document structure, extracts text and tables, exports Markdown. Docling is the first-choice parser; it handles French HR documents with tables, headers, and mixed layouts.
- **VLM local fallback** (SmolVLM2 via Ollama, Windows host) — triggers when Docling fails entirely or returns low confidence. A rendered page image is sent to the local vision-language model, which returns structured JSON with the extracted fields.
- **Pydantic validation** (per-record, Layer 3) — re-instantiates `HRRecord` from the extracted data; any structural or type errors raise a `RED` validation status.

### 2. Extraction (Layer 2)

Raw text from Docling (or JSON from the VLM) is normalised into the canonical schema `HRRecord`:

| Field | Type | Description |
|---|---|---|
| `nom` | `str \| None` | Employee surname |
| `prenom` | `str \| None` | Employee first name |
| `cin` | `str \| None` | National ID number |
| `cnss` | `str \| None` | Social security number |
| `date_embauche` | `str \| None` | Hire date (YYYY-MM-DD) |
| `salaire_brut` | `float \| None` | Gross salary |
| `poste` | `str \| None` | Job title |
| `departement` | `str \| None` | Department |

Regex heuristics and heuristic rules extract each field. Confidence is computed per extractor — Docling confidence from the parser result, VLM confidence fixed at `vlm_default_confidence` (0.6) until measured confidence is implemented.

### 3. Validation (Layer 3 per-record, Pandera per-batch — not yet implemented)

Per-record Pydantic re-instantiation validates type correctness and format constraints (`cin` must match the Algerian national ID pattern, dates must be parseable, salary must be positive, etc.). Per-batch Pandera validation is a reserved interface for future implementation.

### 4. Anomaly Detection (Layer 4 — not yet implemented)

PyOD models (Isolation Forest, ECOD, COPOD) will score extracted records against a population baseline to flag statistical outliers. This layer is reserved for future implementation.

### 5. Status Composition

Every record receives a status along two independent axes, composed with worst-status-wins:

| Extraction status | Validation status | Final status |
|---|---|---|
| GREEN | GREEN | GREEN |
| GREEN | AMBER | AMBER |
| GREEN | RED | RED |
| AMBER | GREEN | AMBER |
| AMBER | AMBER | AMBER |
| AMBER | RED | RED |
| RED | GREEN | RED |
| RED | AMBER | RED |
| RED | RED | RED |

- **GREEN** — extraction confidence ≥ threshold, all required fields present, no missing-field flags, Pydantic validation succeeds.
- **AMBER** — extraction confidence below threshold OR missing required fields detected OR Pydantic validation raises.
- **RED** — extractor failed entirely OR Pydantic raises on structural grounds.

RED is sticky — either axis being RED forces final RED. AMBER is sticky — either axis being AMBER (without RED) forces final AMBER.

### 6. API & Orchestration (Layer 5)

FastAPI serves the upload endpoint (`POST /ingest/upload`). Celery distributes pipeline stages as background tasks. Redis is the brokers and result backend. PostgreSQL stores job state and extracted records.

### 7. Frontend (Layer 6 — Streamlit)

A Streamlit dashboard provides a review interface where a human responsible for HR can inspect each flagged record (score, motif, raw document) and approve or reject it before SIRH write-out.

## Key Architecture Constraints

- **Human-in-the-loop** — no record is pushed to SIRH without explicit human approval. Every anomaly is explained (score + motif).
- **No cloud LLM on real data** — all VLM calls are local (Ollama → SmolVLM2). The architecture stack explicitly prohibits cloud LLM imports (OpenAI, Gemini, Anthropic) on non-synthetic data.
- **Idempotent SIRH writes** — keyed by `doc_id` so re-running the pipeline on the same document is safe.
- **Standardised review statuses** — `approved` / `minor_anomaly` / `critical_error` (🟢/🟡/🔴 in the dashboard). No other statuses are introduced.

## Pipeline Modules

| Module | Responsibility |
|---|---|
| `app/ingestion/docling_path.py` | Runs Docling conversion on a document path; returns extracted Markdown + confidence score + per-field flags |
| `app/ingestion/vlm_path.py` | VLM fallback — converts PDF pages to images, sends to Ollama, parses JSON response into `HRRecord` |
| `app/ingestion/ollama_client.py` | Single entry point for all Ollama calls; base64-encodes image data; sends to `/api/chat`; uses `ExtractPipelineConfig` for URL, model, and timeout |
| `app/ingestion/tasks.py` | Orchestrates the pipeline stages: `ingest_document` → `extract_fields` → `validate_record`; determines extraction status; composes final status via `compose_status()` |
| `app/ingestion/extraction_result.py` | Defines `ExtractionResult` dataclass (record, confidence, source, flags, error code); error constants; `succeeded` property |
| `app/ingestion/schemas.py` | Defines `HRRecord` (Pydantic v2), `RecStatus` enum (GREEN/AMBER/RED), `Flag` model (moteur, detail, score) |
| `app/ingestion/job_state.py` | Projects `HRRecord` + `RecStatus` into `JobState` for API responses; `flags_from_strings` for deserialising stored flags |
| `app/ingestion/repository.py` | In-memory `IngestionJobRepository` (dict CRUD); singleton accessor `get_repository()` |
| `app/core/config.py` | `Settings` (Pydantic BaseSettings), `ExtractPipelineConfig` (extraction subset), `make_extract_pipeline_config()` mapper |
| `app/pipeline/status_composition.py` | `compose_status(extraction, validation) → RecStatus` — worst-status-wins rule |
| `app/api/routes_ingestion.py` | FastAPI routes for upload, status retrieval, and review actions |
| `app/main.py` | FastAPI application factory; entrypoint |

## Configuration (ExtractPipelineConfig)

| Field | Default | Purpose |
|---|---|---|
| `docling_confidence_threshold` | 0.75 | Minimum Docling confidence to skip VLM fallback |
| `ollama_base_url` | `http://127.0.0.1:11434` | Ollama VLM server address |
| `ollama_model` | `richardyoung/smolvlm2-2.2b-instruct:q4_k_m` | VLM model name |
| `ollama_timeout_seconds` | 120 | HTTP timeout for Ollama calls |
| `vlm_default_confidence` | 0.6 | Default confidence assigned to VLM-extracted records |

## Required Fields

Both extractors enforce that the following fields must be present for a record to be considered complete:

- `nom` — surname
- `cin` — national ID number
- `cnss` — social security number
- `date_embauche` — hire date
- `salaire_brut` — gross salary

The VLM extractor currently enforces only the first three (`nom`, `cin`, `cnss`); `date_embauche` and `salaire_brut` are optional for VLM extraction. This divergence is a known gap to reconcile.