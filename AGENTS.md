# AGENTS.md — Outil de Détection des Anomalies dans les Fichiers RH

Ce fichier est lu automatiquement par Copilot CLI et par OpenCode au début de chaque session dans ce dépôt. Il définit le contexte permanent — ne le contourne jamais, même si un prompt ponctuel semble suggérer le contraire.

## Référence unique de vérité

L'architecture complète est dans `docs/architecture.md`. **Avant de générer du code pour une couche donnée, relis la section correspondante de ce document.** Si un prompt te demande quelque chose qui contredit `docs/architecture.md`, signale la contradiction plutôt que de l'ignorer silencieusement.

## Les deux principes non négociables du projet

1. **Human-in-the-loop, jamais boîte noire.** Chaque anomalie détectée doit être explicable (score + motif) et révisable par un responsable RH. N'implémente jamais un chemin qui pousse un enregistrement vers le SIRH sans validation humaine explicite.
2. **Aucune donnée réelle ne quitte l'infrastructure contrôlée.** CIN, CNSS, salaire, données de santé = données personnelles sensibles (RGPD / Loi 09-08). **Interdiction absolue** d'appeler une API LLM cloud (OpenAI, Gemini, Anthropic, etc.) sur des données réelles. Le moteur d'extraction pour les cas ambigus est un **VLM local servi via Ollama** (Qwen2.5-VL 7B ou SmolDocling), jamais un client cloud.

### Vérification automatique à respecter

Avant de considérer une tâche terminée, si tu as touché à `Layer 1` ou `Layer 2`, lance :
```bash
grep -rn "openai\|genai\|import google.generativeai\|anthropic" --include="*.py" . | grep -v "# "
```
Cette commande ne doit rien retourner en dehors de commentaires expliquant explicitement pourquoi ce n'est pas utilisé. Si elle retourne un résultat, corrige avant de continuer.

## Stack technique (ne pas dévier sans le signaler)

| Couche | Outil retenu |
|---|---|
| Ingestion/OCR | PyMuPDF (primaire) → Docling (primaire structuré) → Surya/PaddleOCR (fallback scans) → Tesseract+OCRmyPDF (fallback CPU) → VLM local via Ollama (dernier recours) |
| Extraction/Normalisation | Regex/heuristiques + schéma canonique Pydantic v2 (`HRRecord`) |
| Validation déterministe | Pydantic v2 (par enregistrement) + Pandera (par lot/dataframe) |
| Anomalies statistiques | PyOD (Isolation Forest, ECOD, COPOD) + scikit-learn/statsmodels |
| API & orchestration | FastAPI + Celery + Redis + PostgreSQL |
| Frontend | Streamlit (démo) |

## Conventions de code

- Python 3.11+, type hints partout, `Pydantic v2` (pas v1).
- Un seul point d'entrée pour le VLM local : `ollama_client.py`. Aucun autre fichier n'appelle Ollama directement.
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
