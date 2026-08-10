---
name: hr-anomaly-pipeline
description: Use whenever building, extending, or debugging any layer of the HR document anomaly-detection pipeline (ingestion/OCR, extraction, Pydantic/Pandera validation, PyOD anomaly detection, FastAPI/Celery orchestration, Streamlit dashboard). Loads the canonical architecture and enforces the local-only VLM / no-cloud-LLM constraint before writing code.
---

# Skill : Construire le pipeline de détection d'anomalies RH

## Quand utiliser cette skill
Dès qu'une tâche touche à une des 6 couches du pipeline (`docs/architecture.md`), ou à l'intégration entre deux couches (ex. la sortie de Layer 1 alimente Layer 2).

## Étapes à suivre systématiquement

1. **Relire `docs/architecture.md`** — section correspondant à la couche concernée — avant d'écrire du code.
2. **Vérifier la contrainte "local-only"** si la tâche touche Layer 1 ou Layer 2 : le seul point d'appel LLM autorisé est `app/ingestion/ollama_client.py`. Aucune tâche ne doit ajouter un import `openai`, `google.generativeai`, ou équivalent cloud, même "temporairement pour tester".
3. **Respecter le schéma canonique** `HRRecord` (Pydantic v2) défini dans `app/extraction/schema.py` — ne pas créer un schéma parallèle pour une couche donnée.
4. **Chaque nouvelle règle de validation** (Layer 3) doit être ajoutée soit à `app/validation/rules_pydantic.py` (par enregistrement) soit à `app/validation/rules_pandera.py` (par lot), jamais dans la logique métier de Layer 4 ou 5.
5. **Chaque nouveau détecteur d'anomalie** (Layer 4) doit implémenter l'interface commune `fit / predict / decision_function` (façon PyOD) et retourner un objet `AnomalyResult(score, reason, field)` — jamais un score seul.
6. **Avant de marquer une tâche terminée**, lancer :
   ```bash
   grep -rn "openai\|genai\|anthropic" --include="*.py" app/ | grep -v "^#"
   pytest tests/ -q
   ```
   et confirmer que les deux commandes sont propres.

## Checklist de fin de tâche (à copier dans la review/PR)
- [ ] Le code respecte le schéma `HRRecord` sans le modifier sans discussion.
- [ ] Aucun appel LLM cloud introduit.
- [ ] Chaque anomalie a un score **et** un motif explicable.
- [ ] Les statuts de revue restent `approved` / `minor_anomaly` / `critical_error`.
- [ ] Tests ajoutés sous `tests/` avec au moins un cas limite (donnée manquante, format invalide, doublon).

## Ressources incluses
- `docs/architecture.md` (référence complète, à consulter, pas à dupliquer dans le code).
