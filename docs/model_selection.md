# Model Selection ADR: SmolVLM2

**Date:** 2026-07-30
**Status:** Accepted
**Deciders:** Project team

## Context

The HR Anomaly Detection Pipeline requires a VLM (Vision-Language Model) for extracting structured data from HR PDFs that Docling cannot handle confidently (noisy scans, handwritten text, unusual layouts). The VLM must run locally — no cloud LLM calls on real HR data — and must work on CPU-only hardware typical of a corporate environment.

## Decision

We selected **SmolVLM2** (`richardyoung/smolvlm2-2.2b-instruct:q4_k_m`), served via Ollama, as the default VLM model.

## Options Considered

| Model | Pros | Cons | Why rejected |
|---|---|---|---|
| Qwen2.5-VL 7B (`qwen2.5vl:7b`) | Good extraction quality | Requires ~8–10 GB VRAM; too heavy for CPU-only corporate hardware | Hardware mismatch |
| Unlimited-OCR | Optimized for large documents | Requires GPU; overkill for 1–5 page HR docs | Wrong scale |
| MiniCPM-V | Lightweight | Less accurate on structured HR fields (CIN, CNSS, dates) | Accuracy trade-off |
| Granite | IBM-backed | Heavier than SmolVLM2; marginal accuracy gain for our use case | Unnecessary weight |
| SmolVLM2 | Runs on CPU; sufficient for short HR docs; 2.2B params / 4-bit quant ≈ ~2 GB RAM | Slightly lower accuracy than 7B models on complex layouts | Acceptable trade-off |

## Rationale

1. **CPU-only compatibility** — SmolVLM2 quantized (q4_k_m) fits within ~2 GB RAM and runs without a GPU.
2. **Sufficient accuracy** — For 1–5 page HR documents with structured formats, SmolVLM2's extraction quality is adequate; Docling handles the clean documents and SmolVLM2 covers the edge cases.
3. **Ollama integration** — Clean HTTP API at `http://127.0.0.1:11434`; configured via `ExtractPipelineConfig`.
4. **Low latency** — Fast enough for interactive demo use; acceptable for batch processing in a dev/stage environment.

## Consequences

- All VLM calls in the pipeline use `richardyoung/smolvlm2-2.2b-instruct:q4_k_m` by default.
- The `vlm_default_confidence` is set to `0.6` (lower than Docling's `0.75`) to reflect SmolVLM2's higher baseline uncertainty.
- Users on GPU hardware can swap to Qwen2.5-VL 7B by setting `OLLAMA_MODEL` env var or overriding `ollama_model` in `ExtractPipelineConfig`.