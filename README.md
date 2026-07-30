# HR Anomaly Detection Pipeline

100% open-source, self-hosted Document AI pipeline that intercepts HR PDF documents, extracts structured data, detects anomalies, and surfaces results for human review before any push to the SIRH.

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Ollama** with **SmolVLM2** pulled:
  ```bash
  ollama pull richardyoung/smolvlm2-2.2b-instruct:q4_k_m
  ```
- **Redis** and **PostgreSQL** (or Docker Compose)

### Install & Run

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -e .

# Start Ollama (if not already running)
ollama serve

# Run the pipeline (use venv python to avoid system package conflicts)
python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

### Upload a Document

```bash
curl -X POST "http://127.0.0.1:8000/ingest/upload" \
  -F "file=@sample_hr_document.pdf"
```

Check the result:

```bash
curl -X GET "http://127.0.0.1:8000/ingest/<doc_id>"
```

## Architecture

See `docs/architecture.md` for the full L0–L6 architecture breakdown.

- **Layer 1**: Docling ingestion → SmolVLM2 fallback for low-confidence scans
- **Layer 2**: Regex/heuristic extraction → Pydantic validation
- **Layer 3**: Deterministic validation (Pandera + Pydantic)
- **Layer 4**: Statistical anomaly detection (PyOD)
- **Layer 5**: FastAPI + Celery + Redis orchestration
- **Layer 6**: Streamlit review dashboard

## Model Selection

See `docs/model_selection.md` for the ADR explaining why SmolVLM2 was chosen.

## Testing

```bash
pytest -q
```

All 74 tests should pass.

## Troubleshooting

### `ModuleNotFoundError: No module named 'fastapi'` when running `uvicorn`

This means you are using the system `uvicorn` (at `/usr/bin/uvicorn`) which runs on system Python and doesn't have fastapi installed. 

**Fix:** Always use the venv's python to run uvicorn:
```bash
source .venv/bin/activate
python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

Or without activation:
```bash
.venv/bin/python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

- **No cloud LLM calls on real data** — VLM runs locally via Ollama only
- **Human-in-the-loop** — no record reaches `approved` without explicit RH validation
- **Idempotent SIRH writes** — keyed by `doc_id`