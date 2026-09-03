# HR Anomaly Scaffold — Observability & Free-Tier Deployment Kit

Companion kit for `azizmessaoud/hr-anomaly-scaffold`, built with the STAR
method to add full observability on the OCR/extraction/anomaly pipeline,
CI/CD with Docker, and a $0 deployment path.

## STAR summary

- **Situation**: the scaffold's `JobState`/`AnalysisReport` only show the
  *final* state of a document — no timeline of Docling attempt, RapidOCR
  fallback, validation, and anomaly scoring; nothing to plug into
  Prometheus/Grafana or trace with OpenTelemetry.
- **Task**: instrument every stage once, with one schema, and ship it
  local-first (SQLite + self-hosted Grafana stack) matching the repo's
  "no Redis/Postgres required" demo-mode philosophy.
- **Action**: added `PipelineStageEvent`/`PipelineRunSummary` schemas, an
  `observe_stage()` context manager that feeds OTel spans + Prometheus
  metrics + JSON logs + an OpenLineage event in one call, a `/metrics`
  and `/observability/{doc_id}` endpoint, and a CI/CD + Docker Compose
  stack (API + otel-collector + Tempo + Prometheus + Loki + Grafana).
- **Result**: drop these files into the existing repo, wrap the 4-5
  call sites in `app/ingestion/tasks.py` and `app/anomalies/orchestrator.py`
  with `observe_stage(...)`, and you get full trace/metric/log/lineage
  coverage with zero new required infra and zero cost.

## What's in this kit

```
app/observability/            # PipelineStageEvent, observe_stage(), event store, routes
  schemas.py                 # PipelineStageEvent, PipelineRunSummary, enums
  tracing.py                 # observe_stage() -- the single instrumentation point
  store.py                   # SQLite append-only event store + run summary builder
  routes_observability.py    # GET /observability/{doc_id}, GET /metrics
  otel_setup.py               # OpenTelemetry SDK bootstrap for app/main.py
  lineage.py                  # optional OpenLineage run-event emitter (Marquez/DataHub)
observability/
  otel-collector-config.yaml
  prometheus/prometheus.yml
  grafana/dashboards/hr-pipeline-observability.json
.github/workflows/observability-ci.yml   # test -> build+push GHCR image -> deploy hook
deploy/
  Dockerfile                  # multi-stage, non-root, HEALTHCHECK, HF-Spaces-ready
  docker-compose.observability.yml   # full local observability stack
```

## Why this schema (design rationale)

`PipelineStageEvent` is the single atomic unit. Every stage (`upload_preflight`,
`docling_extraction`, `rapidocr_fallback`, `field_extraction`,
`schema_validation`, `anomaly_detection`, `report_build`) emits exactly one
event with `outcome` (`success | degraded | fallback_used | failed | skipped`),
`duration_ms`, optional `confidence`, and masked error metadata — mirroring
the existing privacy stance in `app/pipeline/report.py` (never expose the
underlying `HRRecord`). `PipelineRunSummary` folds all events for a
`run_id` into the payload the `/observability/{doc_id}` endpoint returns:
full timeline, bottleneck stage, and whether the RapidOCR fallback fired.

This single schema, fed once per stage via `observe_stage()`, projects into
four different observability signals without four different instrumentation
styles:

| Signal | Sink | Question it answers |
|---|---|---|
| Traces | OpenTelemetry -> OTLP -> Tempo | Where did the 4.2s go for this doc_id? |
| Metrics | Prometheus (`hr_pipeline_stage_duration_seconds`, `hr_pipeline_ocr_fallback_total`, `hr_pipeline_documents_processed_total`, `hr_pipeline_anomaly_flags_total`) | What's the p95 latency by stage? How often does OCR fallback rescue a read? |
| Logs | Structured JSON via `logging` | grep/Loki-friendly per-stage log lines |
| Lineage | OpenLineage run events (optional, `OPENLINEAGE_URL`) | Which job/dataset ran, when, with what status — consumable by Marquez/DataHub |

## Integration steps

1. Add dependencies to `pyproject.toml`: `opentelemetry-sdk`,
   `opentelemetry-exporter-otlp-proto-grpc`, `prometheus-client`.
2. In `app/main.py`'s FastAPI factory, call `setup_tracing()` once at
   startup and `app.include_router(observability_router)`.
3. Wrap each stage in `app/ingestion/tasks.py` (Docling call, RapidOCR
   fallback) and `app/anomalies/orchestrator.py` (detector loop) with
   `with observe_stage(doc_id=..., run_id=doc_id, revision=job.revision,
   stage=PipelineStage.DOCLING_EXTRACTION, source="docling") as ctx:` and set
   `ctx["outcome"]`/`ctx["confidence"]` before the block exits.
4. Call `record_document_terminal_status(report.summary.status)` at the
   end of `build_report()`.
5. Run `docker compose -f deploy/docker-compose.observability.yml up` and
   open `http://localhost:3000` (Grafana, admin/admin) to see the dashboard.

## Full pipeline orchestration (target architecture)

```
Client -> POST /ingest/upload
  -> [observe_stage: upload_preflight]
  -> [observe_stage: docling_extraction] -> confidence >= threshold? -> HRRecord
       | below threshold
       v
     [observe_stage: rapidocr_fallback] -> rescued or still-degraded (AMBER)
  -> [observe_stage: schema_validation]  (Pydantic + business rules)
  -> [observe_stage: anomaly_detection]  (rules + statistical cohort detectors)
  -> [observe_stage: report_build]       (AnalysisReport, masked fields)
  -> JobState (in-memory or Postgres in full-stack mode)

Every bracket above is one PipelineStageEvent -> Prometheus + OTel span +
JSON log + optional OpenLineage event, correlated by run_id=doc_id.
```

For asynchronous orchestration once volume grows past the synchronous
FastAPI demo mode, the two most fitting free/open-source orchestrators given
the existing "Celery + Redis, planned" full-stack mode already documented in
`DEPLOYMENT.md` are: keep Celery + Redis (matches the roadmap; task-lifecycle
signals feed into `observe_stage` too), or self-host Prefect 2 OSS server for
a lighter-weight retries/observability UI. Airflow is avoidable — heavier
than this single-document, low-latency use case needs.

## CI/CD with Docker (free tier only)

`.github/workflows/observability-ci.yml` runs on GitHub Actions' free
minutes for public repos: lint (`ruff`), type-check (`mypy`), tests
(`pytest`, excluding `integration`), then builds and pushes a multi-stage
image to GitHub Container Registry (GHCR) — free for public repos, no
extra account needed. A final job calls a deploy-hook URL (Render's free
deploy hooks or a Hugging Face Space webhook) so pushing to `main`
auto-deploys.

`deploy/Dockerfile` is a slim, non-root, multi-stage build with a
`HEALTHCHECK` that reuses the repo's existing `/health/live` endpoint, and
defaults to port 7860 so it works unmodified as a Hugging Face Docker
Space app_port.

## Free deployment options for a public portfolio project

| Path | What you get free | Caveat | Best for |
|---|---|---|---|
| Hugging Face Spaces (Docker SDK) | Public demo URL, GitHub-linked auto-redeploy, good discoverability for a portfolio | Docker Spaces on the free CPU-basic tier require billing/PRO for some accounts as of mid-2026; Gradio/Streamlit SDK Spaces remain free without this restriction | Showing the project to recruiters/community |
| Render free Web Service | 750 free hours/month, deploys straight from your Dockerfile, no card required | Spins down after 15 min idle, 30-50s cold start on next request | An always-reachable but low-traffic API demo |
| Fly.io | — | No longer has a free tier as of 2026; requires a card and ~$2-5/month minimum | Not recommended for a $0 budget |
| Railway | $1/month free credit only | Too small for an always-on API once trial ends | Short-lived demos only |
| GHCR (image hosting) + Render/HF Spaces (compute) | Free image registry, free compute tier pulls the same image | Two moving parts to wire in CI | Cleanest separation of build vs. run in the free-tier stack |

Given the repo is a FastAPI service, the most practical $0 path is: GitHub
Actions builds and pushes to GHCR -> Hugging Face Docker Space (or Render
free Web Service) pulls/redeploys via webhook, with the Grafana/Prometheus
observability stack from `docker-compose.observability.yml` run locally or
on a second free Render service for live demo walkthroughs, since always-on
multi-container observability stacks are the one piece that free PaaS tiers
do not comfortably host together with the API itself.

## Notes and limitations

- The lineage emitter (`lineage.py`) is opt-in and no-ops without
  `OPENLINEAGE_URL`, so it never adds a hard dependency for the demo mode.
- `EventStore` uses SQLite by default; swap the DSN for PostgreSQL only
  when the repo's own "Full-stack mode" (Celery/Redis/Postgres) is adopted.
- HF Docker Spaces free-tier policy for Docker SDK specifically has shifted
  during 2026 for some accounts; verify current terms on the Spaces pricing
  page before depending on it, and keep Render free Web Service as the
  fallback.
