# Architecture

## Scope

This is a local, synchronous pipeline for PDF and image HR documents. It
extracts fields, validates them, detects advisory anomalies, and produces a
report for human review. It does not write to an HRIS.

## Layers

```text
API / CLI
  -> file validation and ingestion
  -> Docling native text or RapidOCR fallback
  -> label-aware normalization
  -> HRRecord and business validation
  -> cohort baselines and anomaly detectors
  -> masked report and decision
```

`app/ingestion/docling_path.py` uses a native PDF text layer when available
and otherwise invokes Docling. `app/ingestion/rapidocr_path.py` handles image
and multi-page scanned inputs. RapidOCR is used after low Docling confidence,
missing required fields, or Docling failure.

`ExtractionResult` is the extractor boundary. `HRRecord` is the canonical
schema. Salary separators are normalized by locale-aware rules; CNSS and
hire-date extraction are label-scoped; non-finite numeric values are rejected.

## Validation and anomaly detection

`validate_hr_record()` emits explainable deterministic details. Pydantic or
coercion failures are blocking. `detect_anomalies()` groups salaries by
department, scores only records with salary and department, then appends the
current salary after scoring. A cohort must reach `MIN_COHORT_SIZE` first.

The current baseline is an in-memory thread-safe store. Isolation Forest and
ECOD are the default detectors. Detector exceptions become reportable signals
instead of pipeline exceptions.

## Data flow

```text
POST /ingest/upload
  -> temporary file checks
  -> ingest_document
  -> extract_fields
  -> validate_record
  -> detect_anomalies
  -> stage_to_job_state + build_report
  -> GET /ingest/{doc_id} or /report
```

`scripts/ingest_directory.py` uses the same flow without HTTP. Each stage
authoritatively carries `doc_id`, `revision`, and `statut`; serialized records
are normalized to those values.

## Status semantics

| Internal status | Meaning |
|---|---|
| `GREEN` | Usable extraction, sufficient confidence, no blocking validation issue. |
| `AMBER` | Usable but requires review because of confidence, completeness, or warnings. |
| `RED` | No usable result or a blocking validation/processing issue. |

| Report decision | Meaning |
|---|---|
| `ACCEPTED` | No blocking or review signal; human approval is still required. |
| `REVIEW_REQUIRED` | Usable record has warnings, detector/baseline issues, or advisory anomalies. |
| `REJECTED` | Usable record has blocking validation/data issues. |
| `FAILED` | Processing failed before a usable record existed. |

Anomaly detection never changes `RecStatus` directly. Anomalous scores,
detector failures, and insufficient baselines are surfaced as review signals;
they must not be presented as clean acceptance.

## Extension rules

- Keep OCR and document processing local.
- Extend `HRRecord` before adding new extracted or cohort fields.
- Keep extractors behind `ExtractionResult`.
- Keep validation rules in `app/pipeline/data_validation.py`.
- New detectors return score, outcome, and reason.
- Replace in-memory repositories only with explicit adapters and tests.
