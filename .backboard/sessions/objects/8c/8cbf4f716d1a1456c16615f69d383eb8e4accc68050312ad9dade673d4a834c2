# AGENTS.md — Outil de Détection des Anomalies dans les Fichiers RH

Ce fichier est lu automatiquement par Copilot CLI et par OpenCode au début de chaque session dans ce dépôt. Il définit le contexte permanent — ne le contourne jamais, même si un prompt ponctuel semble suggérer le contraire.

## Référence unique de vérité

L'architecture complète est dans `docs/architecture.md`. **Avant de générer du code pour une couche donnée, relis la section correspondante de ce document.** Si un prompt te demande quelque chose qui contredit `docs/architecture.md`, signale la contradiction plutôt que de l'ignorer silencieusement.

## Les deux principes non négociables du projet

1. **Human-in-the-loop, jamais boîte noire.** Chaque anomalie détectée doit être explicable (score + motif) et révisable par un responsable RH. N'implémente jamais un chemin qui pousse un enregistrement vers le SIRH sans validation humaine explicite.
2. **Aucune donnée réelle ne quitte l'infrastructure contrôlée.** CIN, CNSS, salaire, données de santé = données personnelles sensibles (RGPD / Loi 09-08). **Interdiction absolue** d'appeler une API LLM cloud (OpenAI, Gemini, Anthropic, etc.) sur des données réelles.

### Vérification automatique à respecter

Avant de considérer une tâche terminée, si tu as touché à `Layer 1` ou `Layer 2`, lance :
```bash
grep -rn "openai\|genai\|import google.generativeai\|anthropic" --include="*.py" . | grep -v "# "
```
Cette commande ne doit rien retourner en dehors de commentaires expliquant explicitement pourquoi ce n'est pas utilisé. Si elle retourne un résultat, corrige avant de continuer.

## Stack technique (ne pas dévier sans le signaler)

| Couche | Outil retenu |
|---|---|
| Ingestion/OCR | PyMuPDF (primaire) → Docling (primaire structuré) → RapidOCR (fallback scans) |
| Extraction/Normalisation | Regex/heuristiques + schéma canonique Pydantic v2 (`HRRecord`) |
| Validation déterministe | Pydantic v2 (par enregistrement) + Pandera (par lot/dataframe) |
| Anomalies statistiques | PyOD (Isolation Forest, ECOD, COPOD) + scikit-learn/statsmodels |
| API & orchestration | FastAPI + Celery + Redis + PostgreSQL |
| Frontend | Streamlit (démo) |

## Conventions de code

- Python 3.11+, type hints partout, `Pydantic v2` (pas v1).
- Chaque détecteur PyOD doit exposer un score **et** un motif lisible par un humain — ne retourne jamais un score brut sans justification dans l'UI de revue.
- Statuts de revue standardisés : `approved` / `minor_anomaly` / `critical_error` (🟢/🟡/🔴 dans le dashboard). N'invente pas d'autres statuts.
- Écritures vers le SIRH : toujours idempotentes, clé = `doc_id`.

## Structure de dépôt attendue

```
.
├── AGENTS.md
├── docs/
│   └── architecture.md
├── .github/skills/hr-anomaly-pipeline/SKILL.md
├── app/
│   ├── ingestion/
│   ├── extraction/
│   ├── validation/
│   ├── anomalies/
│   ├── api/
│   └── dashboard/
├── tests/
└── data/synthetic/        # jeu de test étiqueté — jamais de données réelles ici
```

## Ce qu'il ne faut jamais faire

- Ne jamais committer de document RH réel (CIN/CNSS/salaire réels) dans le dépôt, même pour un test.
- Ne jamais appeler un service cloud sur des données non synthétiques.
- Ne jamais court-circuiter la revue humaine pour "accélérer la démo".
# AGENTS.md — HR Anomaly Scaffold

## Project goal
A local, secure AI pipeline for detecting anomalies in HR files before integration.

## Canonical documents
- `docs/architecture.md` = source of truth for architecture
- `docs/runtime.md` = canonical runtime contracts (modes, endpoints, dependencies, networking). **Start here for any question about "is X required or optional?" or "what happens when Y is down?"**
- `CONTEXT.md` = glossary and current domain decisions

## Runtime truth
- Development happens from Windows PowerShell, but the backend runs inside WSL.
- The Python environment is inside WSL at `.venv`.
- Standard backend startup:
  - `wsl`
  - `source .venv/bin/activate`
  - `python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`
- For runtime contracts, dependency expectations, networking assumptions, and the
  full mode matrix, see **`docs/runtime.md`**. That document is authoritative —
  this file only carries the local dev shell notes.

## Local model setup
- No local LLM models are used in the current pipeline.
- Extraction relies on Docling (structured documents) and RapidOCR (scanned documents).
- Do not add LLM dependencies without updating AGENTS.md and architecture.md.

## Current code seams
- `app/main.py` — app factory seam
- `app/api/health.py` — liveness (`/health/live`) and readiness (`/health/ready`) probes. Contract is in `docs/runtime.md`.
- `app/core/config.py` — config seam (mode-dependent settings)
- `app/ingestion/tasks.py` — orchestration seam for ingestion (fallback policy lives here)
- `app/ingestion/extraction_result.py` — canonical flag vocabulary (`flag_rapidocr_unreachable`, `flag_rapidocr_disabled_in_env`, etc.)
- `app/anomalies/orchestrator.py` — anomaly detection seam (`detect_anomalies: StageResult -> StageResult`)
- `app/anomalies/baseline.py` — cohort baseline store seam (in-memory adapter, swap for Postgres later)
- `app/pipeline/completeness.py` — shared payroll completeness rule (5-field)
- `app/pipeline/status_composition.py` — record status composition seam

## Pipeline flow

```
ingest_document → extract_fields → validate_record → detect_anomalies → stage_to_job_state
```

Each step is a `StageResult -> StageResult` seam. The orchestrator (`tasks.py`) threads the record through these steps. Anomaly detection (`detect_anomalies`) is advisory only — it adds flags but never mutates `RecStatus`.

## Debugging policy
- Reproduce first.
- Patch the narrowest seam.
- Add a regression test.
- Prefer diagnosis over refactors.
- Do not expand scope without saying so.

## Security constraints
- Never send real HR data to cloud models or cloud OCR.
- Never bypass human review.
- Never commit real HR documents.