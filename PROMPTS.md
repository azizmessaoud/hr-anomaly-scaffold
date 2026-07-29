# Prompts complets — à coller dans `copilot` (GitHub Copilot CLI) ou `opencode`

Prérequis avant le premier prompt :
1. Place `AGENTS.md` et `docs/architecture.md` (ton document consolidé) à la racine du dépôt.
2. Place `.github/skills/hr-anomaly-pipeline/SKILL.md` tel quel — les deux outils le liront.
3. Lance l'outil **depuis la racine du dépôt** (`copilot` ou `opencode`), pas depuis un sous-dossier.
4. Vérifie que le fichier est chargé : dans Copilot CLI, tape `/instructions` puis `/skills list` ; dans OpenCode, les fichiers listés dans `"instructions"` de `opencode.json` (ou `AGENTS.md` par défaut) sont chargés au démarrage — redémarre la session après tout changement de config.

---

## Prompt 0 — Scaffold initial (à lancer en premier, une seule fois)

```
Lis AGENTS.md et docs/architecture.md en entier avant de commencer.

Crée le squelette de dépôt suivant, avec des fichiers vides ou minimalement stubés
(pas d'implémentation métier à ce stade, juste la structure + imports + docstrings) :

app/
  ingestion/       (PyMuPDF, Docling, fallback OCR, ollama_client.py)
  extraction/      (schema.py avec le modèle Pydantic HRRecord)
  validation/       (rules_pydantic.py, rules_pandera.py)
  anomalies/        (detectors.py, base interface AnomalyResult)
  api/              (FastAPI app, routes upload/status/results/validate)
  dashboard/        (app Streamlit stub)
tests/
data/synthetic/
pyproject.toml avec les dépendances de docs/architecture.md section 3 (Stack technique)
docker-compose.yml pour Postgres + Redis en local

Ne code aucune logique métier pour l'instant. Objectif : un `pip install -e .` propre
et un `pytest` qui passe (même si les tests sont des placeholders).
```

---

## Prompt 1 — Semaine 1 : Ingestion & OCR

```
Objectif (Semaine 1 de la feuille de route) : implémente Layer 1 — Ingestion & OCR.

Contraintes à respecter (voir AGENTS.md et docs/architecture.md section Layer 1) :
- Chemin principal : PyMuPDF pour texte natif PDF, Docling pour la mise en page
  (tableaux, en-têtes, export Markdown).
- Fallback automatique vers VLM local (Qwen2.5-VL 7B via Ollama) UNIQUEMENT si le
  score de confiance Docling est sous un seuil configurable (`OCR_CONFIDENCE_THRESHOLD`).
- Fallback secondaire vers Surya/PaddleOCR pour les scans de mauvaise qualité,
  et Tesseract+OCRmyPDF comme dernier recours CPU pur.
- Implémente `app/ingestion/ollama_client.py` comme SEUL point d'entrée vers le VLM local.
  Aucun autre fichier ne doit importer ollama directement.
- Écris la fonction de décision de fallback exactement selon la logique documentée
  dans docs/architecture.md (Docling → si confidence >= seuil, utiliser Docling,
  sinon fallback VLM).

Ajoute des tests unitaires avec 2-3 documents PDF synthétiques (à générer, sans
données réelles) couvrant : PDF texte natif propre, PDF scanné basse qualité,
document avec tableau structuré.

À la fin, lance la vérification anti-cloud-LLM du SKILL.md et confirme le résultat.
```

---

## Prompt 2 — Semaine 2 : Extraction & Normalisation

```
Objectif (Semaine 2) : implémente Layer 2 — Extraction & Normalisation.

- Définis le schéma canonique `HRRecord` en Pydantic v2 dans app/extraction/schema.py :
  nom, prénom, CIN, CNSS, date_embauche, salaire_brut, poste, département
  (types et contraintes de base — la validation avancée est Layer 3, pas ici).
- Implémente le parsing regex/heuristique pour les champs à format fixe
  (CIN, CNSS, dates, montants) — voir les formats dans docs/architecture.md Layer 3.
- Pour les layouts non standards : construis le prompt structuré envoyé au VLM local
  (réponse contrainte en JSON), puis fais-le valider par le même modèle HRRecord.
  Un seul chemin de validation, que la source soit OCR classique ou VLM.
- Log chaque appel VLM (document source, prompt, latence, sortie) dans une table
  Postgres dédiée (audit + amélioration future des prompts).

Ajoute des tests couvrant au moins un cas où le parsing regex échoue et bascule
correctement vers le chemin VLM structuré.
```

---

## Prompt 3 — Semaine 3 : Validation déterministe

```
Objectif (Semaine 3) : implémente Layer 3 — Validation déterministe.

Implémente dans app/validation/ les règles suivantes (voir tableau complet dans
docs/architecture.md Layer 3) :
- Format (CIN, CNSS)
- Plage (salaire selon grade, âge 16-70)
- Cohérence croisée (embauche > naissance + 16 ans)
- Unicité (pas de doublon CIN/CNSS dans le lot)
- Complétude (champs obligatoires)
- Référentiel (département existe dans la table de référence)
- Règle métier (salaire >= SMIG, grade manager >= grade employé)

Utilise Pydantic v2 pour les règles par enregistrement (rules_pydantic.py) et
Pandera pour les règles par lot/dataframe (rules_pandera.py), notamment la masse
salariale totale du lot par rapport à un seuil configurable.

Chaque règle violée doit produire une erreur structurée (champ, règle, valeur reçue,
valeur attendue) exploitable par le dashboard — pas juste un booléen pass/fail.

Ajoute un jeu de tests avec au moins un cas positif et un cas négatif par règle.
```

---

## Prompt 4 — Semaine 4 : Détection d'anomalies statistiques

```
Objectif (Semaine 4) : implémente Layer 4 — Anomalies statistiques.

- Utilise PyOD pour Isolation Forest, ECOD et COPOD sur les champs numériques
  (salaire notamment).
- Compare chaque enregistrement contre l'historique RH stocké PAR département/grade/site,
  jamais contre l'ensemble de l'entreprise (voir justification dans docs/architecture.md
  Layer 4 — éviter les faux positifs entre équipes différentes).
- Chaque détecteur doit implémenter l'interface commune définie dans le SKILL.md
  (fit/predict/decision_function) et retourner un AnomalyResult(score, reason, field).
- Combine les scores des différents détecteurs en un score de risque global, mais
  garde la traçabilité individuelle de chaque détecteur dans la sortie — le
  réviseur RH doit pouvoir voir "pourquoi" pour chaque signal, pas juste le score final.

Ajoute des tests avec un jeu de données synthétique contenant des anomalies de
salaire injectées volontairement, et vérifie qu'elles sont détectées avec un motif
cohérent.
```

---

## Prompt 5 — Semaine 5 : API, orchestration & dashboard

```
Objectif (Semaine 5) : implémente Layer 5 (API & Orchestration) et Layer 6 (Dashboard).

Layer 5 :
- FastAPI : endpoints upload, statut du job, résultats, validation manuelle.
- Celery + Redis pour le traitement asynchrone par lot.
- PostgreSQL pour les métadonnées documents, enregistrements extraits, anomalies,
  décisions de validation.

Layer 6 :
- Dashboard Streamlit : upload, tableau des anomalies avec statuts
  🟢 approved / 🟡 minor_anomaly / 🔴 critical_error, export, et bouton de validation
  humaine explicite avant tout passage vers "Approuvé".
- Aucun enregistrement ne doit pouvoir passer au statut "approved" sans une action
  humaine explicite dans le dashboard — vérifie ce point en particulier.

Ajoute un test d'intégration bout-en-bout : upload d'un document synthétique →
job Celery → résultat visible dans le dashboard → validation manuelle → écriture
idempotente simulée vers le SIRH (clé = doc_id).
```

---

## Prompt 6 — Semaine 6 : Tests, cas limites, jeu de test étiqueté

```
Objectif (Semaine 6) : durcissement et mesure.

- Génère 20-30 documents RH synthétiques (jamais de données réelles) couvrant :
  cas standards, cas avec anomalies de salaire, CIN/CNSS mal formés, doublons,
  documents scannés de mauvaise qualité, écriture manuscrite (pour forcer le
  fallback VLM).
- Étiquette-les (anomalie attendue : oui/non, type d'anomalie).
- Mesure et rapporte séparément la précision d'extraction pour Docling seul vs.
  pour le fallback VLM, comme demandé dans docs/architecture.md section 5.
- Relance la vérification anti-cloud-LLM globale sur tout le dépôt.
- Résume les limites connues (débit adapté à une démo, pas à l'échelle entreprise
  sans GPU supplémentaire) dans un README.md à la racine.
```

---

## Prompt utilitaire — Audit de conformité (à relancer à tout moment)

```
Audite tout le dépôt pour vérifier les deux principes non négociables d'AGENTS.md :
1. Aucun appel à une API LLM cloud sur du code touchant des données réelles.
2. Aucun chemin de code qui pousse un enregistrement vers le SIRH sans validation
   humaine explicite (statut "approved" posé uniquement via une action utilisateur
   dans le dashboard).

Liste chaque fichier suspect avec la ligne concernée, sans corriger automatiquement —
je veux valider chaque cas avant modification.
```
