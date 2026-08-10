## Destination

Replace the VLM (Ollama) fallback engine with RapidOCR (onnxruntime) throughout the ingestion pipeline: remove `vlm_path.py`, `ollama_client.py`, all VLM-specific error codes/flags/config fields, and the VLM fallback logic in `tasks.py` and `health.py`, while preserving the Docling-first-with-fallback architecture and the `ExtractionResult` boundary contract.

## Notes

- Domain: Python HR-anomaly-detection pipeline, Écluse (PFA), built during a SopraHR internship.
- Repo: github.com/azizmessaoud/hr-anomaly-scaffold (local clone, no tracker previously configured — defaulting to the local-markdown tracker).
- Standing constraints that bind every decision here: no cloud APIs (local-only, no exception — this is *why* the VLM is being removed, not despite it), CPU-only hardware (i5-10310U, 16GB RAM, no GPU), human-in-the-loop is non-negotiable (no ticket may propose auto-approval).
- Consult `/grilling` and `/domain-modeling` for decision tickets; `/research` for the RapidOCR API question.
- Session-0 findings already folded in below: Docling's path is text→regex→HRRecord via `parser_regex.py`, *not* structured extraction — RapidOCR (also raw-text OCR) is the same shape as Docling's path, not the VLM's JSON-coercion shape. `pyproject.toml` deps live under `[dependency-groups].main`, not `[tool.uv]`.

## Decisions so far

- [RapidOCR return shape](01_rapidocr_return_shape.md) — RapidOCR returns `(det_lines, det_confidences)` or `(None, None)`; use mean of per-line recognition confidences as document-level `confidence`
- [Persisted source VLM](02_persisted_source_vlm.md) — no persisted data stores `source="vlm"`; no migration needed
- [Error taxonomy and source type](03_error_taxonomy_and_source_type.md) — replace VLM error constants with RapidOCR-specific ones; `ExtractionSource = Literal["docling", "rapidocr"]`; `flag_vlm_fallback` → `flag_rapidocr_fallback`
- [Test rewrite strategy](04_test_rewrite_strategy.md) — hybrid: 1:1 rename for preserved patterns, restructure for RapidOCR-specific failure modes; `test_vlm_path.py` deleted
- [RapidOCR PDF input](05_rapidocr_pdf_input.md) — RapidOCR needs PDF→numpy array rasterization; reuse `_pdf_to_image` approach adapted to return numpy array directly
- [Doc update scope](06_doc_update_scope.md) — same-pass updates for AGENTS.md, README.md, docs/architecture.md; deferred for the rest

## Not yet specified

<!-- fog of war: in-scope questions that are still dim after the 6 tickets below -->

- The L1/L2 boundary question (regex extraction in ingestion vs. a separate extraction layer) — depends on how the taxonomy decision in [Error taxonomy and source type](03_error_taxonomy_and_source_type.md) resolves; not sharp enough to ticket until then.
- Whether the new extraction engine should be a single `rapidocr_path.py` module or split into OCR + post-processing — depends on the RapidOCR return-shape research ([RapidOCR return shape](01_rapidocr_return_shape.md)).
- The full doc-update scope across 9+ files — [Doc update scope](06_doc_update_scope.md) identifies the files but the actual edit pass should wait for code stability.
- `docs/runtime.md` and `docs/runtime-spec.md` contain extensive VLM/Ollama runtime contracts (mode matrix, fallback policy table, flag glossary, config table) that will need a full rewrite pass once the taxonomy decision is locked.

## Out of scope

- Wiring real L3 validation rules into `validate_record()` — separate, pre-existing effort, unrelated to the OCR fallback engine.
- Resolving the L1/L2 boundary question in general — only in-scope insofar as this refactor's module design bears on it.
- Updating `docs/runtime-spec.md` and `docs/runtime.md` beyond the sections that reference VLM/Ollama in the extraction pipeline — those runtimes are affected but the runtime contract itself (modes, endpoints, health probes) follows from the taxonomy decision.
- The `docs/LAYER1_IMPLEMENTATION_REPORT.md` refresh — already known-stale independent of this refactor; fold in if the doc is touched for other reasons, otherwise defer to a separate ticket.