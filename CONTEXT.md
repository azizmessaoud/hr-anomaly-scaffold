# Domain Glossary — HR Anomaly Detection Pipeline

## OCR Engine Selection

The primary extraction engine is **Docling** (IBM), with **RapidOCR** (ONNX Runtime) as the fallback for scanned or low-quality documents.

Docling handles structured documents (printed forms, tables, headers) while RapidOCR provides a lightweight fallback that runs on CPU without GPU requirements.

| Field | Description |
|---|---|
| `docling_confidence_threshold` | Minimum Docling confidence to trigger RapidOCR fallback |
| `rapidocr_enabled` | Whether RapidOCR fallback is enabled |
| `rapidocr_default_confidence` | Default confidence score assigned to RapidOCR-extracted records (0.6) |

## Status Axes

The pipeline assesses quality along two independent axes, each producing a `RecStatus` (`GREEN` / `AMBER` / `RED`).

### `status_extraction` (extraction axis)

Determined by the orchestrator from `ExtractionResult` properties:

- **GREEN** — confidence ≥ threshold AND all required fields present, no missing-field flags
- **AMBER** — confidence below threshold OR missing required fields detected
- **RED** — extractor failed entirely (exception or `erreur_traitement` set)

### `status_validation` (validation axis)

Determined by Pydantic validation in `validate_record()`:

- **GREEN** — `HRRecord` re-instantiation succeeds
- **RED** — Pydantic raises (malformed data, invalid formats, wrong types)

## Status Composition

The final `RecStatus` is produced by composing the two axes with `compose_status(extraction, validation) → RecStatus`.

The composition rule is **worst-status-wins**:

| extraction | validation | result |
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

Key properties:
- RED is sticky — either axis being RED forces final RED
- AMBER is sticky — either axis being AMBER (without RED) forces final AMBER
- GREEN only when both axes are GREEN

This ensures that an extraction flagged as low-confidence (AMBER) is never promoted to GREEN by a successful validation pass.

## compose_status

The function implementing the two-axis composition rule, located in `app/pipeline/status_composition.py`. It is used by `validate_record()` in `tasks.py` to combine `stage.statut` (extraction quality, determined by `_determine_extraction_status()`) with the validation result after Pydantic re-instantiation.

## Anomaly Detection (Layer 4)

Statistical anomaly detection runs after validation, behind the `detect_anomalies` seam (`app/anomalies/orchestrator.py`). It is **advisory only** — flags are added to the record but `RecStatus` is never mutated. The human reviewer decides.

| Term | Description |
|---|---|
| `cohort_key` | Tuple grouping records for baseline comparison. Currently `(departement,)`. |
| `CohortBaselineStore` | Append-only, thread-safe in-memory store of salary values per cohort. |
| `detect_anomalies` | `StageResult -> StageResult` seam called after `validate_record`. |
| `AnomalyResult` | One detector's verdict: score, outcome (`ANOMALOUS` / `NOT_ANOMALOUS` / `BASELINE_UNAVAILABLE` / `SKIPPED`), and reason. |
| `MIN_COHORT_SIZE` | Minimum cohort samples before detectors run (default: 10). |
| Detectors | `IsolationForestDetector` and `ECODDetector` (PyOD wrappers). |

Key properties:
- Anomaly detection never mutates `RecStatus` — flags only.
- A failed detector is surfaced as a flag, not an exception.
- Records without `salaire_brut` or `departement` skip anomaly detection.
- The salary is appended to the baseline *after* scoring (never scored against itself).

## Pipeline Flow

```
ingest_document → extract_fields → validate_record → detect_anomalies → stage_to_job_state
```

Each step is a `StageResult -> StageResult` seam. The orchestrator (`tasks.py`) is the thin dispatcher that threads the record through these steps.

## Key Code Locations

| Term | Location |
|---|---|
| `ExtractPipelineConfig` | `app/core/config.py` |
| `make_extract_pipeline_config()` | `app/core/config.py` |
| `compose_status()` | `app/pipeline/status_composition.py` |
| Extraction status determination | `app/ingestion/tasks.py::` `_determine_extraction_status()` |
| Final composition in pipeline | `app/ingestion/tasks.py::validate_record()` |
| Anomaly orchestrator | `app/anomalies/orchestrator.py::detect_anomalies()` |
| Baseline store | `app/anomalies/baseline.py::CohortBaselineStore` |
| Detectors | `app/anomalies/detectors.py` |
| Cohort key | `app/anomalies/cohort.py::cohort_key()` |