# Domain Glossary — HR Anomaly Detection Pipeline

## ExtractPipelineConfig

A frozen Pydantic model (`app/core/config.py`) that captures all extractor-specific configuration parameters:

| Field | Description |
|---|---|
| `docling_confidence_threshold` | Minimum Docling confidence to skip VLM fallback |
| `ollama_base_url` | Base URL for the local Ollama VLM server |
| `ollama_model` | Model name served by Ollama |
| `ollama_timeout_seconds` | HTTP timeout for Ollama calls |
| `vlm_default_confidence` | Default confidence score assigned to VLM-extracted records |

Constructed from `Settings` via `make_extract_pipeline_config()`. Never pulls `Settings()` inside extractors — all extractor-specific config flows through this object explicitly (candidate 3 fix).

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

## Key Code Locations

| Term | Location |
|---|---|
| `ExtractPipelineConfig` | `app/core/config.py` |
| `make_extract_pipeline_config()` | `app/core/config.py` |
| `compose_status()` | `app/pipeline/status_composition.py` |
| Extraction status determination | `app/ingestion/tasks.py::` `_determine_extraction_status()` |
| Final composition in pipeline | `app/ingestion/tasks.py::validate_record()` |
| Single source for VLM calls | `app/ingestion/ollama_client.py::extract_hr_fields()` |