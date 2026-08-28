# Deployment Guide

The recommended deployment for this student project is one local WSL/Linux
process. It matches the synchronous FastAPI runtime and avoids unnecessary
infrastructure.

## Local setup

Requirements: Python 3.11, WSL2/Linux/macOS, disk/RAM for Docling and OCR,
and the system libraries installed by the Python dependencies.

```bash
cd /mnt/c/Users/amessaoud/Desktop/hr-anomaly-scaffold
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[main,dev]'
```

The `main` extra installs FastAPI, Docling, RapidOCR, Pillow, PyOD, and the
data stack. The `dev` extra installs pytest, Ruff, and mypy.

## Configuration

Create `.env` only for local overrides:

```dotenv
APP_NAME=hr-anomaly-pipeline
DEBUG=false
RAPIDOCR_ENABLED=true
RAPIDOCR_MODEL_PATH=models/rapidocr/en_ppocr_server_v2.0_infer.onnx
RAPIDOCR_TIMEOUT_SECONDS=30
RAPIDOCR_DEFAULT_CONFIDENCE=0.6
DOCLING_CONFIDENCE_THRESHOLD=0.75
MAX_UPLOAD_SIZE_BYTES=10485760
```

RapidOCR uses packaged models by default. The configured model path is used
when it points to an existing local override. Jobs and anomaly baselines are
currently in memory; there is no database to configure.

## Start and monitor

```bash
python -m uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl -sS http://127.0.0.1:8000/health/live
curl -sS http://127.0.0.1:8000/health/ready
```

Logs show processing failures. Reports show status, severity, rule, and
column counts. Missing Docling is a hard readiness failure (`503`); missing
optional RapidOCR is reported as degraded.

## Ingest documents

API path:

```bash
RESPONSE=$(curl -sS -X POST http://127.0.0.1:8000/ingest/upload \
  -F 'file=@data/synthetic/hr_record_01.pdf')
echo "$RESPONSE"
DOC_ID=$(printf '%s' "$RESPONSE" | python -c 'import json,sys; print(json.load(sys.stdin)["doc_id"])')
curl -sS "http://127.0.0.1:8000/ingest/$DOC_ID/report"
```

Directory path with JSON output:

```bash
python scripts/ingest_directory.py data/synthetic --output-dir outputs/reports
find outputs/reports -type f -name '*.json' -print
```

## Tests

```bash
./scripts/run_focused_tests.sh
python -m pytest -q -m 'not integration'
python -m compileall -q app tests scripts
```

Optional real OCR tests:

```bash
python -m pytest -q -m integration
python -m pytest -q tests/integration/test_ocr_integration.py::TestRapidOCRIntegration::test_rapidocr_extracts_text_from_synthetic_pdf
```

Integration tests can be slow or unavailable when model/runtime dependencies
are missing. That does not invalidate parser, API, validation, and mocked OCR
tests.

## Optional Docker demo

The local path is primary. A minimal demonstration image can use:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e '.[main]'
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t hr-anomaly-pipeline .
docker run --rm -p 8000:8000 hr-anomaly-pipeline
```

Docker does not add persistence. Do not add PostgreSQL or Redis until actual
adapters and migrations exist.
