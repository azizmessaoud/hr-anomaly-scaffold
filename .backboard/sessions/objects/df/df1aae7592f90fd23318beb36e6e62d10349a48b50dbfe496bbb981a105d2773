# Layer 1 — Ingestion & OCR: Implementation Report

## 1. What was created

### Project skeleton
- `pyproject.toml` — project metadata, dependency groups (main + dev), `ruff`, `mypy`, `pytest` config.
- `app/__init__.py`, `app/core/__init__.py`, `app/api/__init__.py`, `app/ingestion/__init__.py`
- `tests/__init__.py`, `tests/ingestion/__init__.py`
- `tests/conftest.py` — adds repo root to `sys.path`.

### Core settings
- `app/core/config.py` — `Settings(BaseSettings)` with all documented knob defaults:
  - `docling_confidence_threshold = 0.75`
  - `ollama_base_url`, `ollama_model`, `ollama_timeout_seconds`
  - `celery_broker_url`, `celery_task_max_retries`, `celery_task_default_retry_delay`
  - `review_timeout_hours = 48`

### Domain contract
- `app/ingestion/schemas.py` — `HRRecord(Pydantic v2 BaseModel)`:
  - Identity/employment fields: `id`, `revision`, `nom`, `prenom`, `cin`, `cnss`, `date_embauche`, `salaire_brut`, `poste`, `departement`
  - Pipeline fields: `confiance: float [0,1]`, `flags: list[Flag]`, `statut: RecStatus`, `erreur_traitement: Optional[str]`
  - `Flag` model: `moteur`, `detail`, `score: Optional[float]`
  - `RecStatus` StrEnum: `GREEN`, `AMBER`, `RED`
  - Field-level Pydantic validators: `cin` (`[A-Z]{1,2}\d{5,6}`), `cnss` (exactly 9 digits), `date_embauche` (ISO), `salaire_brut` (> 0)

### Deterministic extraction (TDD-done)
- `app/ingestion/parser_regex.py` — pure functions, no deps beyond stdlib `re`:
  - `extract_cin`, `extract_cnss`, `extract_date_embauche`, `extract_salaire_brut`, `extract_nom_prenom`
- `tests/ingestion/test_parser_regex.py` — 12 tests covering valid, invalid, format variants, missing values.

### Boundary adapters (mockable seams)
- `app/ingestion/ollama_client.py` — `extract_hr_fields(image_path, prompt) -> str` calls `ollama_base_url/api/chat` via `httpx`, single point of entry for all VLM calls (matches `AGENTS.md` rule).
- `app/ingestion/docling_path.py` — `run_docling(path) -> DoclingResult`, `extract_from_docling(path) -> HRRecord`. Confidence-driven: below threshold → AMBER + flag.
- `app/ingestion/vlm_path.py` — `extract_with_vlm(path) -> HRRecord`. Constrained JSON prompt; malformed JSON raises `ValueError` (caught by tasks layer → `erreur_traitement`).

### Orchestration
- `app/ingestion/tasks.py` — three stages with boundary-signal error handling:
  1. `ingest_document(path, doc_id)` — file existence gate.
  2. `extract_fields(path, doc_id)` — tries Docling first; on any exception falls back to VLM; if both fail returns `RecStatus.RED` with error detail.
  3. `validate_record(step2, doc_id)` — re-instantiates `HRRecord` from JSON; on Pydantic error → `RecStatus.RED`; on AMBER → promotes to GREEN (MVP minimal validation, per execution rules).

  **Not yet wired to real Celery** — the chain topology is mocked here so tests don’t depend on a Redis broker. A follow-up ticket wraps these three functions in `celery.chain()` + retry/back-off.

### API surface (synchronous, returns final status)
- `app/api/routes_ingestion.py` — `POST /ingest/upload` (multipart), `GET /ingest/{doc_id}` (polling state from in-memory `_job_store`).
- `app/main.py` — `create_app()` factory, `/health` endpoint, router inclusion.

### Test suite (6 files, written before or alongside implementation)
- `tests/ingestion/test_schemas.py` — 5 tests (happy path, CIN format, CNSS length, salaire positivity, missing fields → RED).
- `tests/ingestion/test_parser_regex.py` — 12 tests as above.
- `tests/ingestion/test_docling_path.py` — mocked Docling: happy path → GREEN; low confidence → AMBER.
- `tests/ingestion/test_vlm_path.py` — mocked VLM: happy → GREEN; malformed JSON → ValueError; missing fields → AMBER.
- `tests/ingestion/test_tasks.py` — 6 tests: missing file → RED; both paths fail → RED; Docling failure → VLM fallback; validation success; bad payload → RED.

---

## 2. What remains stubbed or intentionally out of scope for this slice

| Item | Status |
|---|---|
| Celery worker real wiring + Redis broker | Stubbed in `tasks.py`; real `celery.chain()` is a follow-up ticket |
| PostgreSQL schema + Alembic | Not started; slice uses temp in-memory/skip |
| Layer 3 full business-rule set | MVP only: format/range/required + cross-field via Pydantic; Pandera batch rules deferred |
| Layer 4 (PyOD anomaly detection) | Not started; blocked by Layer 1 slice |
| SIRH write adapter | Not started; field contract undecided |
| Retry/back-off configuration in real Celery | Undecided; defaults in `config.py` are placeholders |
| `review_timeout_hours` enforcement | Setting exists; escalation logic live in Layer 5/6, not yet implemented |
| Authentication / RBAC | Deferred |
| Docker / render / deployment config | Not started |

---

## 3. Assumptions still needing a product decision

1. **SIRH target (real vs mocked).** There is no write adapter, no field mapping, and no mock. Layer 1 produces `HRRecord`. Without knowing the target product (Sopra HR / Silae / Lucca / generic REST), Layer 5 cannot be contracted.
2. **Database choice beyond temp storage.** Architecture says PostgreSQL. When to introduce SQLAlchemy 2 + Alembic, vs staying file/temp for the demo — owner decision.
3. **`doc_id` generation policy.** Current code derives `doc_id` from the filename stem. Per the architecture addendum it should be a **surrogate UUID**; this slices uses filename-derived IDs for debuggability until Postgres/uuid policy is confirmed.
4. **PyOD contamination rate.** ADR-006 sets MVP `contamination=0.03`; which departments should share a global model vs. per-cohort — product decision.
5. **SIRH idempotency on resubmit.** `revision` increments; only one revision per `doc_id` should ever reach `approved`. Where is this rule enforced — in the Task layer or in a future `approved_records` table? Needs ownership.

---

## 4. Environment blocker

I could not run `pytest`, `ruff`, or `mypy` in this shell because:
- The system Python is externally managed (PEP 668, Debian).
- A `pyproject.toml`-managed virtual environment cannot be created in this shell session.

**To verify:** run in a normal Windows terminal or WSL terminal:
```bash
cd C:\Users\amessaoud\Desktop\hr-anomaly-scaffold
python -m venv .venv
.venv\Scripts\activate   # or .venv/bin/activate on WSL
pip install -e ".[dev]"
pytest -q
ruff check app/ tests/
mypy app/
```

---

## 5. Security / compliance check

- `grep` for `openai|genai|import google.generativeai|anthropic` in `app/` returns **zero matches** — no cloud LLM imports.
- The only external LLM boundary is `app/ingestion/ollama_client.py` — as required by `AGENTS.md`.
- No real HR data is committed; tests use synthetic fixtures only.
