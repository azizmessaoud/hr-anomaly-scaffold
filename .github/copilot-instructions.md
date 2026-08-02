# Copilot Instructions — HR Anomaly Scaffold

You are working on a local, secure HR anomaly detection backend.

## Priorities
- Optimize for small, safe, testable patches.
- Prefer diagnosis before editing.
- Avoid token waste: read only the files needed for the current task.
- Never rewrite large areas unless asked.

## Non-negotiables
- No cloud LLM/API calls on real HR data.
- Local-first architecture only.
- Human review is mandatory before any HRIS integration.
- Follow `docs/architecture.md`, `AGENTS.md`, and `CONTEXT.md`.

## Runtime environment
- Code runs in WSL inside a Python virtual environment.
- Before running the backend, always assume this sequence:
  1. `wsl`
  2. `source .venv/bin/activate`
  3. `python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`
- Do not assume PowerShell commands work inside WSL.
- Do not assume Windows localhost is reachable from WSL for Ollama/vLLM.
- If local model calls fail, check host binding and Windows-to-WSL connectivity first.

## Repo map
- `app/main.py` — FastAPI app factory
- `app/core/` — configuration
- `app/ingestion/` — ingestion and extraction paths
- `app/pipeline/` — pipeline helpers and status composition
- `tests/` — regression tests
- `docs/architecture.md` — canonical design
- `CONTEXT.md` — domain glossary and current decisions

## Tool usage
- Prefer file reading and code search before proposing edits.
- Prefer terminal commands for reproducible diagnosis.
- Prefer the smallest set of files possible.
- If MCP tools exist, use them only when they reduce repo reading or provide exact external context.
- Do not use MCP for broad exploration when local file inspection is enough.

## Debug loop
1. Restate the bug in one sentence.
2. Identify the likely module seam.
3. Reproduce with the smallest command.
4. Inspect only the directly relevant files.
5. Propose the smallest fix.
6. Add or update a regression test.

## Planning loop
1. Restate the target behavior.
2. Name the interface to change.
3. Name the exact files to touch.
4. List risks.
5. List tests to add first.

## Coding rules
- Python 3.11+, type hints, Pydantic v2.
- Keep interfaces small and explicit.
- Prefer dependency injection.
- Avoid hidden globals.
- Keep Ollama access behind one client module.
- Do not invent new status semantics beyond documented ones.