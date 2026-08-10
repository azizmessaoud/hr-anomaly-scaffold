## Question

`extraction_result.py` currently defines `ERR_VLM_MALFORMED_JSON`, `ERR_VLM_NOT_OBJECT`, `ERR_VLM_MISSING_REQUIRED_FIELD`, `ERR_VLM_INVALID_NUMERIC`, `ERR_VLM_UNREACHABLE`, and `flag_vlm_fallback()`. None of the JSON-parsing failure modes apply to RapidOCR (it never returns JSON to malform). What's the replacement taxonomy — e.g. `ERR_RAPIDOCR_NO_TEXT` (OCR engine produced nothing), `ERR_RAPIDOCR_MISSING_REQUIRED_FIELD` (regex found no match for a required field after OCR), plus whatever `flag_rapidocr_fallback()` is named — and does `ExtractionSource = Literal["docling", "vlm"]` become `Literal["docling", "rapidocr"]` or something that anticipates future engines?

This is the central module-design decision. It touches `extraction_result.py`, `tasks.py`, `job_state.py`, `_needs_vlm_fallback` (rename), `_stage_from_docling_preserved` (which carries VLM-domain flag helpers), `_determine_extraction_status` (source comparison), and the flag factory functions. The answer also gates what the test-rewrite strategy looks like (04).

Label: wayfinder:grilling
Blocking: 01 (need to know RapidOCR's failure modes to design the taxonomy)

## Answer

**Error taxonomy replacement:**

| Old VLM constant | New RapidOCR constant | Rationale |
|---|---|---|
| `ERR_VLM_MALFORMED_JSON` | **Removed** | RapidOCR never returns JSON to malform |
| `ERR_VLM_NOT_OBJECT` | **Removed** | RapidOCR never returns JSON objects |
| `ERR_VLM_MISSING_REQUIRED_FIELD` | `ERR_RAPIDOCR_MISSING_REQUIRED_FIELD` | Same semantic, different source |
| `ERR_VLM_INVALID_NUMERIC` | **Removed** | Numeric validation still happens in `HRRecord` Pydantic model, not in the extractor |
| `ERR_VLM_UNREACHABLE` | `ERR_RAPIDOCR_UNREACHABLE` | Transport-level failure (engine not available) |
| `ERR_FILE_MISSING` | `ERR_FILE_MISSING` | Unchanged |
| `ERR_DOCLING_FAILED` | `ERR_DOCLING_FAILED` | Unchanged |
| `ERR_DOCLING_PARSE_FAILED` | `ERR_DOCLING_PARSE_FAILED` | Unchanged |

**New RapidOCR-specific constant:**
- `ERR_RAPIDOCR_NO_TEXT = "rapidocr_no_text"` — OCR engine produced no text at all (returned `(None, None)`)

**Flag renames:**
- `flag_vlm_fallback()` → `flag_rapidocr_fallback()` — returns `"rapidocr_fallback"`
- `flag_vlm_unreachable()` → `flag_rapidocr_unreachable()` — returns `"rapidocr_unreachable"`
- `flag_vlm_disabled_in_env()` — unchanged (still returns `"vlm_disabled_in_env"`; this is a config-level flag, not an engine-level one, and the name signals the intent clearly)
- `flag_low_confidence()` — unchanged
- `flag_docling_low_confidence_review()` — unchanged
- `flag_missing_fields()` — unchanged

**ExtractionSource:** `Literal["docling", "rapidocr"]` — no need to anticipate future engines; the taxonomy is explicit and the codebase doesn't have a plugin architecture for extractors.

**Resolution**: 2026-08-08. Central module-design decision resolved. The new taxonomy removes VLM-specific JSON-parsing errors and adds RapidOCR-specific `ERR_RAPIDOCR_NO_TEXT`. All flag names are renamed to be engine-agnostic or RapidOCR-specific. `ExtractionSource` becomes `Literal["docling", "rapidocr"]`.
