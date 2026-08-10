# Repository Understanding — HR Anomaly Detection Pipeline

## 1. Repository Overview

This is a **100% open-source, self-hosted Document AI pipeline** that intercepts HR PDF documents (contracts, pay slips, etc.), extracts structured personal and employment data from them, validates the extracted records through deterministic rules and statistical anomaly detection, and only releases approved records toward the SIRH/payroll system after a human reviewer has signed off.

**Core principle**: No data leaves the controlled infrastructure. No cloud LLM is called on real documents.

## 2. Architecture

### High-Level Architecture

The system follows a **layered pipeline architecture** with six conceptual layers:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 6: Streamlit Dashboard (Human Review)                 │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: FastAPI + Celery + Redis (Orchestration)           │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: PyOD (Statistical Anomaly Detection)               │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Pydantic + Pandera (Deterministic Validation)      │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Regex/Heuristics (Extraction & Normalisation)      │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Docling + SmolVLM2 via Ollama (Ingestion & OCR)    │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Human-in-the-loop, never a black box** — every anomaly must be explainable (score + motif) and revisable by an HR responsible.
2. **No data leaves controlled infrastructure** — CIN, CNSS, salary, health data = sensitive personal data (GDPR / Law 09-08). Absolute prohibition on cloud LLM calls on real data.
3. **Docling primary, VLM local fallback** — Docling handles structured documents; SmolVLM2 via Ollama handles scans/low-confidence cases.
4. **Idempotent SIRH writes** — keyed by `doc_id` so re-running the pipeline on the same document is safe.

## 3. Codebase Map

### Project Structure

```
hr-anomaly-scaffold/
├── AGENTS.md                    # Permanent context for AI agents
├── CONTEXT.md                   # Domain glossary & status axes
├── README.md                    # Quick start & architecture overview
├── pyproject.toml               # Dependencies & tooling config
├── .gitignore                   # Standard Python gitignore
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app factory & entrypoint
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes_ingestion.py  # POST /upload, GET /{doc_id}
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py            # Settings, ExtractPipelineConfig
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── doc_id.py            # UUID generation & validation
│   │   ├── docling_path.py      # Docling extraction path
│   │   ├── extraction_result.py # ExtractionResult boundary contract
│   │   ├── job_state.py         # JobState API response model
│   │   ├── ollama_client.py     # Single Ollama HTTP entry point
│   │   ├── parser_regex.py      # Regex field extractors
│   │   ├── repository.py        # In-memory job store
│   │   ├── schemas.py           # HRRecord, RecStatus, Flag models
│   │   ├── tasks.py             # Pipeline orchestrator
│   │   └── vlm_path.py          # VLM extraction fallback path
│   └── pipeline/
│       ├── __init__.py
│       └── status_composition.py # compose_status() worst-status-wins
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Path setup for imports
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── test_api_contract.py # API shape parity tests
│   │   ├── test_doc_id.py       # UUID generation tests
│   │   ├── test_docling_path.py # Docling extraction tests
│   │   ├── test_parser_regex.py # Regex extractor tests
│   │   ├── test_repository.py   # In-memory store tests
│   │   ├── test_schemas.py      # Pydantic model tests
│   │   ├── test_tasks.py        # Pipeline orchestrator tests
│   │   └── test_vlm_path.py     # VLM fallback tests
│   └── pipeline/
│       ├── __init__.py
│       └── test_status_composition.py # Status composition tests
└── docs/
    ├── architecture.md          # Full L0-L6 architecture
    ├── model_selection.md       # SmolVLM2 ADR
    ├── system-record.md         # System description
    └── LAYER1_IMPLEMENTATION_REPORT.md
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `app/main.py` | FastAPI application factory; entrypoint |
| `app/api/routes_ingestion.py` | Upload endpoint & status polling |
| `app/core/config.py` | Settings (Pydantic BaseSettings), ExtractPipelineConfig |
| `app/ingestion/tasks.py` | Pipeline orchestrator: ingest → extract → validate → compose status |
| `app/ingestion/docling_path.py` | Docling extraction: PDF → Markdown → regex fields |
| `app/ingestion/vlm_path.py` | VLM fallback: PDF → image → Ollama → JSON → fields |
| `app/ingestion/ollama_client.py` | Single entry point for all Ollama calls |
| `app/ingestion/parser_regex.py` | Regex field extractors (CIN, CNSS, date, salary, name) |
| `app/ingestion/extraction_result.py` | ExtractionResult boundary contract & error constants |
| `app/ingestion/schemas.py` | HRRecord, RecStatus, Flag Pydantic models |
| `app/ingestion/job_state.py` | JobState API response model |
| `app/ingestion/doc_id.py` | UUID generation & validation |
| `app/ingestion/repository.py` | In-memory job store (dict CRUD) |
| `app/pipeline/status_composition.py` | compose_status() worst-status-wins rule |

## 4. Main Workflows

### Upload Workflow

```
POST /ingest/upload
    ↓
generate_doc_id() → UUID
    ↓
Save uploaded file to /tmp/hr-anomaly-uploads/{doc_id}_{filename}
    ↓
run_ingestion_pipeline(document_path, doc_id, revision)
    ↓
ingest_document() → check file exists
    ↓
extract_fields() → Docling primary, VLM fallback
    ↓
validate_record() → Pydantic re-instantiation
    ↓
stage_to_job_state() → JobState projection
    ↓
repository.save(job)
    ↓
Return JobState to client
```

### Extraction Workflow

```
extract_fields(document_path, doc_id, revision)
    ↓
extract_from_docling(document_path) → ExtractionResult
    ↓
If succeeded AND confidence ≥ threshold:
    → return StageResult.from_extraction(docling_result)
    ↓
If failed OR confidence < threshold:
    → extract_with_vlm(document_path) → ExtractionResult
    ↓
If VLM succeeded:
    → return StageResult.from_extraction(vlm_result)
    ↓
If both failed:
    → return StageResult(terminal=True, statut=RED)
```

### Status Determination

```
_determine_extraction_status(result, threshold)
    ↓
If not succeeded OR record is None → RED
    ↓
If source == "docling" AND confidence < threshold → AMBER
    ↓
If any flag.moteur == source AND "manquant" in flag.detail → AMBER
    ↓
Otherwise → GREEN
```

### Status Composition

```
compose_status(extraction, validation) → RecStatus
    ↓
If either is RED → RED (sticky)
    ↓
If either is AMBER → AMBER (sticky)
    ↓
Otherwise → GREEN
```

## 5. Environment Setup in WSL

### Virtual Environment

The project uses a Python virtual environment located at `.venv/` within the WSL filesystem.

**Activation command**:
```bash
source .venv/bin/activate
```

**Deactivation**:
```bash
deactivate
```

### Running the Server

**Correct way** (using venv Python):
```bash
source .venv/bin/activate
python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

**Incorrect way** (system Python):
```bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000  # WRONG - uses system Python
```

**Why the distinction matters**: The system Python at `/usr/bin/uvicorn` doesn't have fastapi installed. Always use `python -m uvicorn` from within the activated venv.

### Path Handling

- **Windows paths**: `/mnt/c/Users/amessaoud/Desktop/hr-anomaly-scaffold/`
- **WSL paths**: `/mnt/c/Users/amessaoud/Desktop/hr-anomaly-scaffold/`
- **Ollama URL**: `http://127.0.0.1:11434` (Windows host accessible from WSL)
- **Uploaded files**: `/tmp/hr-anomaly-uploads/{doc_id}_{filename}`

### Dependencies

Installed in the venv via:
```bash
pip install -e .
```

Key dependencies from `pyproject.toml`:
- **Main**: fastapi, uvicorn, celery, redis, pydantic, docling, pymupdf, ollama, pandas, pandera, pyod, scikit-learn, statsmodels, Pillow
- **Dev**: pytest, pytest-cov, ruff, mypy, httpx

## 6. Testing and Validation

### Running Tests

```bash
source .venv/bin/activate
pytest -q
```

All **74 tests** should pass.

### Test Structure

| Test File | Coverage |
|---|---|
| `test_schemas.py` | HRRecord Pydantic validation (CIN, CNSS, salary, date) |
| `test_doc_id.py` | UUID generation & validation |
| `test_parser_regex.py` | Regex field extractors |
| `test_docling_path.py` | Docling extraction path |
| `test_vlm_path.py` | VLM fallback path |
| `test_tasks.py` | Pipeline orchestrator (ingest → extract → validate) |
| `test_status_composition.py` | compose_status() worst-status-wins rule |
| `test_api_contract.py` | API shape parity (upload → polling) |
| `test_repository.py` | In-memory job store |

### Test Patterns

- **Mocking**: External dependencies (Docling, Ollama) are mocked at the call site
- **Fixtures**: `fake_document`, `fake_image`, `test_config` provide test data
- **Assertions**: Tests verify status (GREEN/AMBER/RED), flags, and error codes

### Key Test Cases

1. **Status composition**: 9 combinations of extraction × validation statuses
2. **VLM fallback**: Docling failure triggers VLM; both failing returns RED
3. **AMBER not promoted to GREEN**: Validation never elevates AMBER to GREEN
4. **RED is sticky**: Validation doesn't rescue RED
5. **API contract**: Upload and polling return identical 6-field JobState

## 7. Design Decisions

### Configuration Architecture

Two-tier config:
- **Settings** (Pydantic BaseSettings): All config including Celery, Ollama, review timeout
- **ExtractPipelineConfig** (Pydantic BaseModel): Extraction-only subset, frozen/immutable

The pipeline modules receive `ExtractPipelineConfig`; `Settings()` is only used once in `_get_config()`.

### Status Assignment

- **Extractors** (docling_path.py, vlm_path.py) never set `statut` on `HRRecord`
- **Orchestrator** (`_determine_extraction_status()`) is the sole authority for extraction status
- **Validator** (`validate_record()`) composes extraction + validation via `compose_status()`

### Error Handling

- **ExtractionResult** is the boundary contract between extractors and orchestrator
- **`erreur_traitement`** carries typed error codes (e.g., `vlm_malformed_json`, `docling_failed`)
- **`succeeded`** property: `record is not None AND erreur_traitement is None`

### Flag System

- **`Flag` model**: `moteur` (engine), `detail` (free-text), `score` (optional)
- **Orchestrator carries flags as strings** to avoid coupling to `Flag` shape
- **`flags_from_strings()`** converts to `Flag(moteur="pipeline", detail=<name>)` for API

## 8. Terminology / Glossary Notes

| Term | Definition | Location |
|---|---|---|
| `RecStatus` | Status enum: GREEN / AMBER / RED | `app/ingestion/schemas.py` |
| `HRRecord` | Canonical extraction result schema | `app/ingestion/schemas.py` |
| `Flag` | Anomaly/metadata marker with engine, detail, score | `app/ingestion/schemas.py` |
| `ExtractionResult` | Boundary contract for extractors | `app/ingestion/extraction_result.py` |
| `StageResult` | Pipeline transport object between stages | `app/ingestion/tasks.py` |
| `JobState` | API response model (6-field contract) | `app/ingestion/job_state.py` |
| `doc_id` | Surrogate UUID for idempotent SIRH writes | `app/ingestion/doc_id.py` |
| `revision` | Increments on resubmission within a doc_id | `app/ingestion/doc_id.py` |
| `confidence` | Extraction quality score (0.0–1.0) | `app/ingestion/schemas.py` |
| `manquant` | French for "missing" — used in flag detail strings | `app/ingestion/docling_path.py`, `vlm_path.py` |
| `vlm_fallback` | Flag indicating VLM was used instead of Docling | `app/ingestion/extraction_result.py` |
| `low_confidence` | Flag indicating confidence below threshold | `app/ingestion/extraction_result.py` |
| `erreur_traitement` | Typed error code for pipeline failures | `app/ingestion/extraction_result.py` |
| `succeeded` | Property: record present AND no error | `app/ingestion/extraction_result.py` |
| `compose_status` | Worst-status-wins rule for two axes | `app/pipeline/status_composition.py` |
| `_determine_extraction_status` | Orchestrator status logic | `app/ingestion/tasks.py` |
| `_REQUIRED_FIELDS` | Required fields for extraction completeness | `app/ingestion/docling_path.py`, `vlm_path.py` |

## 9. Risks and Improvements

### Current Risks

1. **`"manquant"` string coupling**: Status determination parses French substring in flag details — fragile if wording changes
2. **`_REQUIRED_FIELDS` divergence**: Docling requires 5 fields; VLM requires 3 — silent inconsistency
3. **`ERR_VLM_MALFORMED_JSON` collision**: Three distinct failure domains (image conversion, Ollama HTTP, JSON parse) share one error code
4. **VLM confidence conflation**: VLM always gets confidence=0.6 regardless of extraction quality
5. **`_config` global state**: Module-level config cache makes testing non-default configs difficult
6. **`_pdf_to_image()` silent failure**: Returns None on any error with no diagnostic information
7. **`mkstemp` fd leak**: File descriptor never closed in `_pdf_to_image()`

### Improvement Opportunities

1. **Add `FlagCategory` enum**: Replace string matching with structured flag types
2. **Shared `_REQUIRED_FIELDS`**: Extract to a single constant used by both extractors
3. **Distinct VLM error codes**: Separate image conversion, Ollama HTTP, and JSON parse errors
4. **VLM confidence measurement**: Implement per-field confidence scoring instead of fixed 0.6
5. **Dependency injection for config**: Replace module-level global with explicit parameter
6. **Structured error messages**: Replace free-text `erreur_traitement` with typed error objects

## 10. Final Summary

This is a **well-structured, testable Document AI pipeline** with clear separation of concerns:

- **Extraction layer** (docling_path.py, vlm_path.py) produces `ExtractionResult` boundary contracts
- **Orchestration layer** (tasks.py) coordinates stages and determines status
- **Validation layer** (status_composition.py) composes two independent quality axes
- **API layer** (routes_ingestion.py) exposes upload and polling endpoints
- **Storage layer** (repository.py) persists job state

The codebase follows Python best practices (type hints, Pydantic v2, pytest) and has good test coverage (74 tests). The main architectural friction points are around string-based flag coupling and inconsistent required-field contracts between extractors.

**Key strength**: The `ExtractionResult` boundary contract cleanly separates extraction from orchestration, making both layers independently testable.

**Key weakness**: The `Flag` model's free-text `detail` field creates implicit contracts between modules that can drift silently.
