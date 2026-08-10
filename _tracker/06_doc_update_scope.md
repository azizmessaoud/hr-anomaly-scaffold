## Question

Nine files reference vlm/ollama outside `app/`: `AGENTS.md`, `CONTEXT.md`, `README.md`, `.github/copilot-instructions.md`, `.github/skills/hr-anomaly-pipeline/SKILL.md`, `docs/architecture.md`, `docs/model_selection.md`, `docs/repository-understanding.md`, `docs/system-record.md`, `docs/LAYER1_IMPLEMENTATION_REPORT.md`. Which get updated in the same pass as the code change (the ones a reader would hit first — `AGENTS.md`, `README.md`, `docs/architecture.md`) versus deferred to a follow-up docs pass? `docs/LAYER1_IMPLEMENTATION_REPORT.md` is already known-stale independent of this refactor — worth folding its refresh in here, or keeping that a separate ticket entirely?

## Answer

**Updated in the same pass** (reader-facing, hit first):
- `AGENTS.md` — update the VLM/OCR fallback chain and the single-entry-point rule
- `README.md` — update the demo mode + VLM fallback section to reflect RapidOCR replacement
- `docs/architecture.md` — update the architecture diagram and model selection table

**Deferred to a follow-up docs pass**:
- `CONTEXT.md` — update the VLM model selection glossary entry
- `docs/model_selection.md` — this is the SmolVLM2 ADR; it should be closed/retired since the model choice is being replaced
- `docs/repository-understanding.md` — update the Layer 1 description
- `docs/system-record.md` — update the extraction engine references
- `docs/LAYER1_IMPLEMENTATION_REPORT.md` — already known-stale; update if touched for other reasons
- `.github/copilot-instructions.md` — update the WSL/Ollama networking note (becomes moot with RapidOCR)
- `.github/skills/hr-anomaly-pipeline/SKILL.md` — update the local-only constraint description

**Resolution**: 2026-08-08. Same-pass updates for AGENTS.md, README.md, docs/architecture.md. Deferred for the rest.
