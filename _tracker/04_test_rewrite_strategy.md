## Question

`test_tasks.py` has ~15 cases built around mocking `extract_with_vlm` and asserting on `flag_vlm_fallback()` / `ERR_VLM_*` values (low-confidence-triggers-fallback, docling-failure-triggers-fallback, fallback-failure-returns-RED, etc.). Do we do a 1:1 mechanical rename (mock `extract_with_rapidocr` in the same shape), or restructure the cases because RapidOCR's failure modes are genuinely different (no "malformed JSON" or "not an object" case, but a new "OCR ran, produced text, regex still found nothing" case that has no VLM analogue)? Also covers what happens to `test_vlm_path.py` (delete outright, since there's no code left to test) and the stray `ollama_model="qwen2.5vl:7b"` fixture value in `test_docling_path.py` (leftover from the old known model-mismatch issue, unrelated to this refactor but touched by the same file).

The voter decision on taxonomy (03) determines whether the 1:1 rename is possible or restructuring is needed.

## Answer

**Test rewrite strategy: hybrid — 1:1 rename for VLM→RapidOCR cases, restructure for the new failure mode.**

1. **`test_vlm_path.py` — DELETE outright.** No code left to test after removing `vlm_path.py` and `ollama_client.py`.

2. **`test_tasks.py` — restructure, not just rename.** The VLM fallback cases need to be replaced with RapidOCR fallback cases:
   - Remove all cases mocking `extract_with_vlm` and asserting on `flag_vlm_fallback()`, `ERR_VLM_*`, `flag_vlm_unreachable()`, `flag_vlm_disabled_in_env()`.
   - Add cases for RapidOCR fallback:
     - Docling success + RapidOCR fallback (low confidence) → preserved Docling result, AMBER, `rapidocr_fallback` flag
     - Docling failure + RapidOCR success → RapidOCR result, status per confidence/completeness
     - Docling failure + RapidOCR failure (no text) → RED, `rapidocr_no_text` error code
     - Docling failure + RapidOCR failure (missing required fields) → RED, `rapidocr_missing_required_field` error code
     - `VLM_ENABLED=false` (now `RAPIDOCR_ENABLED=false`) → skip RapidOCR, preserve Docling
     - RapidOCR unreachable → AMBER, preserve Docling, `rapidocr_unreachable` flag
   - Keep the `_stub_config` helper but rename `vlm_enabled` to `rapidocr_enabled`.
   - The stray `ollama_model="qwen2.5vl:7b"` fixture in `test_docling_path.py` should be cleaned up (removed or replaced with `rapidocr_model`).

3. **`test_extraction_result.py` — rename VLM flag tests to RapidOCR flag tests.**
   - `test_flag_vlm_fallback_is_stable_string` → `test_flag_rapidocr_fallback_is_stable_string`
   - `test_flag_vlm_unreachable_is_stable_string` → `test_flag_rapidocr_unreachable_is_stable_string`
   - `test_flag_vlm_disabled_in_env_is_stable_string` → keep as-is (config-level flag, unchanged name)
   - Add `test_flag_rapidocr_fallback_is_stable_string` and `test_flag_rapidocr_unreachable_is_stable_string`

4. **`test_health.py` — update VLM health probe tests to RapidOCR health probe tests.**
   - Replace `vlm_enabled` config toggles with `rapidocr_enabled`
   - Replace `vlm` check references with `rapidocr`

5. **`test_docling_path.py` — clean up the stray `ollama_model="qwen2.5vl:7b"` fixture.** Replace with `rapidocr_model` or remove the Ollama-related config fields entirely since they're no longer relevant to the Docling path test.

**Resolution**: 2026-08-08. Hybrid strategy: 1:1 rename for preserved patterns, restructure for RapidOCR-specific failure modes. `test_vlm_path.py` deleted. Stray Ollama fixture cleaned up.
