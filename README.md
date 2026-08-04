# HR Anomaly Detection Pipeline

100% open-source, self-hosted Document AI pipeline that intercepts HR PDF documents, extracts structured data, detects anomalies, and surfaces results for human review before any push to the SIRH.

## Quick Start

The pipeline has two runtime modes (see `docs/runtime.md` for the full contract). **The default for new users is the synchronous, in-memory demo mode** — Docling-only, no broker, no Postgres.

### Demo mode (Docling-only) — recommended for new users

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run the pipeline (use venv python to avoid system package conflicts)
python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

That's it. The pipeline now accepts uploads at `POST /ingest/upload` and
runs Docling on each document. No Ollama, Redis, or Postgres needed for
the demo path.

If you don't have Docling installed yet, the readiness probe
(`/health/ready`) will return 503 — install `docling` and restart.

### Demo mode + VLM fallback

To enable the VLM (Ollama) fallback path, install Ollama and pull the
SmolVLM2 model:

```bash
ollama pull richardyoung/smolvlm2-2.2b-instruct:q4_k_m
ollama serve  # if not already running
```

Then start the backend with the **Windows host IP** for
`OLLAMA_BASE_URL` (WSL cannot reach Ollama at `127.0.0.1`):

```bash
# Inside WSL, find the Windows host IP
WIN_HOST_IP=$(awk '/nameserver/ {print $2; exit}' /etc/resolv.conf)
export OLLAMA_BASE_URL="http://${WIN_HOST_IP}:11434"

python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

If the host IP doesn't work, verify the Windows firewall allows inbound
TCP on port 11434 from the WSL virtual NIC. See `docs/runtime.md` for
the full networking contract.

If you'd rather skip VLM entirely:

```bash
export VLM_ENABLED=false
python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

The pipeline will keep using Docling and classify low-confidence
extractions as AMBER (reviewable).

### Full-stack mode (planned, not yet shipped)

Full-stack mode (Celery + Redis + Postgres) is on the roadmap. Once
shipped, `docs/runtime.md` will document the dependency expectations.
Today, demo mode is the supported path.

## Upload a Document

```bash
curl -X POST "http://127.0.0.1:8000/ingest/upload" \
  -F "file=@sample_hr_document.pdf"
```

Check the result:

```bash
curl -X GET "http://127.0.0.1:8000/ingest/<doc_id>"
```

Check pipeline health:

```bash
curl -sS http://127.0.0.1:8000/health/live   # process liveness
curl -sS http://127.0.0.1:8000/health/ready  # mode-aware readiness
```

## Architecture

See `docs/architecture.md` for the full L0–L6 architecture breakdown.

- **Layer 1**: Docling ingestion → SmolVLM2 fallback for low-confidence scans
- **Layer 2**: Regex/heuristic extraction → Pydantic validation
- **Layer 3**: Deterministic validation (Pandera + Pydantic)
- **Layer 4**: Statistical anomaly detection (PyOD)
- **Layer 5**: FastAPI + Celery + Redis orchestration
- **Layer 6**: Streamlit review dashboard

## Runtime contract

For endpoint dependency tables, the mode matrix, and the canonical
flag vocabulary, see **`docs/runtime.md`**.

## Model Selection

See `docs/model_selection.md` for the ADR explaining why SmolVLM2 was chosen.

## Testing

```bash
pytest -q
```

All tests should pass.

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

### `ollama` connection refused from WSL

In WSL, `127.0.0.1` points to WSL's own loopback. Use the Windows host
IP for `OLLAMA_BASE_URL` (see "Demo mode + VLM fallback" above).

### Readiness probe returns 503

`/health/ready` returns 503 only when a hard demo-mode dependency
(Docling) is missing. Install `docling` via `pip install docling` and
restart the server. Optional deps going down never flips to 503.

---

- **No cloud LLM calls on real data** — VLM runs locally via Ollama only
- **Human-in-the-loop** — no record reaches `approved` without explicit RH validation
- **Idempotent SIRH writes** — keyed by `doc_id`