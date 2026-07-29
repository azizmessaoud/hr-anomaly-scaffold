# Architecture Complète — Outil de Détection des Anomalies dans les Fichiers RH

**Destination.** Un "pare-feu de données" 100% open-source et auto-hébergeable qui intercepte les documents RH (PDF/images), les transforme en données structurées via une pipeline Document AI, applique un contrôle à deux niveaux (règles déterministes + anomalies statistiques), et ne laisse passer vers le SIRH/paie que les enregistrements validés et revus par un humain.

**Deux principes non négociables** (repris et renforcés de la v2) :
1. **Human-in-the-loop, jamais boîte noire** — chaque anomalie doit être explicable et révisable par un responsable RH.
2. **Les données ne quittent jamais l'infrastructure contrôlée** — CIN, CNSS, salaire, données de santé = données personnelles sensibles (RGPD / Loi 09-08). Aucun appel à une API cloud (gratuite ou payante) sur des données réelles tant qu'un DPA n'est pas signé. C'est pourquoi le moteur LLM par défaut est un **VLM local**, pas Gemini.

---

## 0bis. Mapping avec le framework générique "8 étapes"

Un framework générique de construction de système IA circule souvent en 8 étapes (choisir le LLM → framework → données → embeddings → vector DB → RAG → outils/API → modèles locaux), avec une couche de gouvernance par-dessus. Voici comment votre projet s'y positionne concrètement — et où il s'en écarte volontairement.

| Étape générique | Dans votre projet | Décision |
|---|---|---|
| 1. Choisir le LLM | Pas de LLM cloud (GPT/Claude/Gemini) sur données réelles | **VLM local** : Qwen2.5-VL 7B ou SmolDocling, servi via **Ollama** ou **vLLM** |
| 2. Framework IA | LangChain/LangGraph optionnels | Pipeline explicite (Docling → validation → PyOD), orchestré en Celery ; LangGraph seulement si le cahier des charges l'exige |
| 3. Collecte/traitement des données | Crawl4AI, Firecrawl, Docling, Unstructured, LlamaParse | **Docling** retenu (structure tableaux/en-têtes, export Markdown) ; pas de crawling web, vos données arrivent en upload |
| 4. Embeddings | OpenAI Embeddings, Sentence Transformers | **Non pertinent ici** — ce projet ne fait pas de recherche sémantique sur un corpus, il traite des enregistrements structurés au fil de l'eau. Pas de RAG nécessaire |
| 5. Vector DB | Pinecone, OpenSearch | **Non nécessaire** dans le cœur du produit. Utile uniquement en option pour la détection de doublons "quasi-identiques" (ex. `pgvector` local dans Postgres pour repérer un même employé saisi sous deux orthographes) |
| 6. Pipeline RAG | — | **Non applicable** : votre outil valide des données extraites, il ne répond pas à des questions ouvertes sur un corpus documentaire |
| 7. Connecter outils/API | Function calling, agents, MCP | **API SIRH** en sortie uniquement (écriture des enregistrements approuvés) ; pas d'agent autonome qui déclenche des actions non supervisées |
| 8. Modèles open-source/locaux | vLLM, LocalAI, NVIDIA NIM | **Confirmé** : c'est votre chemin par défaut, pas une option de repli |

**À retenir** : la plupart des étapes 4–6 (embeddings, vector DB, RAG) appartiennent à un cas d'usage différent — un assistant qui répond à des questions sur une base de connaissances. Votre outil est un pipeline de validation/détection sur des enregistrements structurés ; l'inclure quand même ajouterait de la complexité sans bénéfice pour le mémoire ou la démo. Ne les ajoutez pas juste parce qu'ils figurent dans un framework générique.

---

## 1. Vue d'ensemble du pipeline

```
[Upload PDF/Image]
        │
        ▼
┌───────────────────┐
│ Layer 1 — Ingestion│  PyMuPDF / pdf2image (PDF → image si scanné)
│   & OCR/Layout      │  Docling (primaire) + Surya/PaddleOCR (fallback scans)
│                     │  Local VLM (Qwen2.5-VL 7B / SmolDocling via Ollama)
│                     │  → fallback uniquement si confiance Docling basse
└─────────┬───────────┘
          ▼
┌───────────────────┐
│ Layer 2 — Extraction│  Regex/heuristiques pour champs standards
│   & Normalisation   │  Sortie VLM contrainte en JSON pour cas complexes
│                     │  → schéma canonique HR (Pydantic)
└─────────┬───────────┘
          ▼
┌───────────────────┐
│ Layer 3 — Validation│  Pydantic v2 (par enregistrement)
│   déterministe       │  Pandera (au niveau dataframe / lot)
└─────────┬───────────┘
          ▼
┌───────────────────┐
│ Layer 4 — Anomalies │  PyOD (Isolation Forest, ECOD, COPOD)
│   statistiques      │  scikit-learn / statsmodels pour séries temporelles
└─────────┬───────────┘
          ▼
┌───────────────────┐
│ Layer 5 — API &     │  FastAPI + Celery + Redis (jobs async)
│   Orchestration     │
└─────────┬───────────┘
          ▼
┌───────────────────┐
│ Layer 6 — Frontend  │  Streamlit (démo) OU FastAPI + React/shadcn (prod)
│   Dashboard revue   │  Vert / Jaune / Rouge → validation humaine → intégration
└─────────┬───────────┘
          ▼
   [SIRH / Paie / ERP]   ← uniquement les enregistrements "Approuvé"

┌───────────────────────────────────────────────────────────┐
│ Layer 0 — Sécurité (transversal) : chiffrement au repos,   │
│ contrôle d'accès, journal d'audit immuable, rétention      │
└───────────────────────────────────────────────────────────┘
```

---

## 2. Détail par couche

### Layer 0 — Sécurité & conformité (transversal, à traiter dès le jour 1)
- Chiffrement au repos (Postgres avec chiffrement disque, ou SQLCipher pour SQLite).
- Contrôle d'accès par rôle (RH standard vs RH admin vs auditeur lecture seule).
- Journal d'audit immuable : qui a validé quoi, quand, avec quel score de confiance — obligatoire pour la traçabilité RH.
- Politique de rétention des documents sources alignée sur votre calendrier légal RH.
- **Aucune donnée réelle envoyée à une API cloud** (Gemini, OpenAI, etc.) sans DPA signé. Utilisez des documents synthétiques/anonymisés pour tout test avec un service cloud.

### Layer 1 — Ingestion & OCR / Document Intelligence
| Outil | Rôle | Statut |
|---|---|---|
| **PyMuPDF (fitz)** | Extraction texte natif des PDF, conversion page → image | Primaire, local |
| **Docling (IBM)** | Compréhension de mise en page : tableaux, en-têtes, ordre de lecture, export Markdown | Primaire pour documents imprimés/structurés |
| **Surya / PaddleOCR** | OCR sur photos de mauvaise qualité, mise en page complexe | Fallback documents scannés/photographiés |
| **Tesseract + OCRmyPDF** | Baseline CPU pur, sans dépendance GPU | Fallback ultime si aucune ressource GPU |
| **VLM local (Qwen2.5-VL 7B ou SmolDocling, via Ollama)** | Extraction directe en JSON pour cas ambigus (écriture manuscrite, mise en page inhabituelle) | Fallback déclenché uniquement si le score de confiance Docling est bas |

Logique de déclenchement :
```
Docling(document) → confidence_score
if confidence_score >= threshold:
    utiliser sortie Docling
else:
    utiliser VLM local en fallback (Ollama)
```

Cela garde le chemin principal rapide et déterministe, et réserve le coût GPU/latence du VLM aux cas réellement difficiles.

### Layer 2 — Extraction & Normalisation
- Schéma canonique défini en **Pydantic v2** (`HRRecord`) : nom, prénom, CIN, CNSS, date d'embauche, salaire brut, poste, département.
- Parsing par regex/heuristiques pour les champs à format fixe (CIN, CNSS, dates, montants).
- Pour les layouts non standards : prompt structuré envoyé au VLM local, réponse contrainte en JSON, puis validée par le même modèle Pydantic — pas de traitement différencié entre sortie OCR classique et sortie VLM, tout converge vers le même schéma.

### Layer 3 — Validation déterministe
| Type de règle | Exemple |
|---|---|
| Format | CIN correspond à `[A-Z]{1,2}\d{5,6}`, CNSS = 9 chiffres |
| Plage | Salaire dans les bornes du grade, âge 16–70 ans |
| Cohérence croisée | Date d'embauche postérieure à date de naissance + 16 ans |
| Unicité | Pas de doublon CIN/CNSS dans le lot |
| Complétude | Tous les champs obligatoires présents |
| Référentiel | Code département existe dans la table de référence |
| Règle métier | Salaire ≥ SMIG, grade manager ≥ grade employé |

- **Pydantic** pour la validation par enregistrement.
- **Pandera** pour la validation au niveau du dataframe/lot (ex. masse salariale totale du lot ne dépasse pas un seuil). Pandera est recommandé plutôt que Great Expectations ici : bien plus léger à configurer pour un projet de cette taille, tout en couvrant les mêmes besoins (schémas de colonnes, contraintes de plage, vérifications personnalisées).

### Layer 4 — Détection d'anomalies statistiques
- **PyOD** comme bibliothèque principale — API unifiée façon scikit-learn (`fit`, `predict`, `decision_function`) sur plus de 60 détecteurs.
- Modèles recommandés pour données RH :
  - **Isolation Forest** — anomalies de salaire, combinaisons inhabituelles.
  - **ECOD** — sans hyperparamètre, bon sur petits jeux de données.
  - **COPOD** — rapide, bon pour données multivariées.
- Comparaison contre l'historique RH stocké (par département/grade/site) plutôt que contre l'ensemble de l'entreprise, pour éviter les faux positifs liés à des différences légitimes entre équipes.
- Chaque détecteur produit un score + un motif ; combinez-les en un score de risque global mais gardez la traçabilité de **pourquoi** chaque anomalie a été signalée — indispensable pour que le réviseur RH comprenne la décision.

### Layer 5 — API & Orchestration
- **FastAPI** : endpoints upload, statut du job, résultats, validation manuelle.
- **Celery + Redis** : traitement asynchrone par lot, pour ne pas bloquer les requêtes HTTP sur des PDF volumineux.
- Optionnel : **LangGraph** uniquement si vous voulez démontrer une logique de retry/fallback formalisée (ex. si l'extraction échoue, boucler vers un autre moteur automatiquement). Pour un projet de stage, une machine à états explicite dans Celery suffit et est plus simple à défendre à l'oral — n'ajoutez LangGraph que si le cahier des charges demande explicitement une orchestration agentique.
- **PostgreSQL** : métadonnées documents, enregistrements extraits, anomalies, décisions de validation.

### Layer 6 — Frontend / Dashboard
- **Streamlit** — chemin rapide, dashboard fonctionnel avec upload, tableau des anomalies, export, en un dixième du code React. Recommandé pour se concentrer sur la logique IA/ML.
- **FastAPI + Next.js/shadcn** — chemin production si le stage exige authentification utilisateur et une interface "SaaS".
- Statuts de revue : 🟢 Validé (prêt pour intégration) / 🟡 Anomalie mineure (revue requise) / 🔴 Erreur critique (rejeté).

### Intégration finale
- Seuls les enregistrements **Approuvé** sont poussés vers le SIRH via son API.
- Écritures idempotentes (clé = doc_id) pour éviter les doublons en cas de retry.
- Journal complet : qui a approuvé, score de confiance de l'extraction, référence au fichier source.

---

## 3. Stack technique — récapitulatif

| Couche | Outil | Licence | Coût |
|---|---|---|---|
| PDF/Image | PyMuPDF, pdf2image, Pillow | Open source | Gratuit |
| Document AI | Docling | Open source (IBM) | Gratuit |
| OCR fallback scans | Surya, PaddleOCR | Open source | Gratuit |
| OCR fallback CPU | Tesseract + OCRmyPDF | Apache 2.0 | Gratuit |
| VLM local | Qwen2.5-VL 7B ou SmolDocling (via Ollama) | Open source | Gratuit, local |
| Modélisation données | Pydantic v2 | MIT | Gratuit |
| Validation lot | Pandera | Apache 2.0 | Gratuit |
| Anomalies | PyOD, scikit-learn, statsmodels | BSD | Gratuit |
| Backend | FastAPI | MIT | Gratuit |
| Jobs async | Celery + Redis | BSD | Gratuit (local) |
| Base de données | PostgreSQL (local ou Supabase free) | Open source | Gratuit |
| Frontend démo | Streamlit | Apache 2.0 | Gratuit |
| Frontend prod | Next.js + shadcn/ui | MIT | Gratuit |
| Déploiement | Docker + Render/HF Spaces (démo uniquement, jamais données réelles) | — | Gratuit |

---

## 4. Contraintes matérielles à documenter

- Qwen2.5-VL 7B en 4-bit nécessite ~8–10 Go de VRAM ; CPU seul fonctionne mais lentement (secondes à minutes par page). SmolDocling est assez léger pour tourner sur CPU.
- Vérifiez la disponibilité du modèle choisi dans la bibliothèque Ollama avant de vous engager ; sinon utilisez `transformers`/`vLLM` directement.
- Débit adapté à une démo/projet de stage (dizaines à quelques centaines de documents) ; ne passe pas à l'échelle entreprise sans GPU supplémentaire — à mentionner explicitement comme limite connue dans le rapport, pas comme un défaut.

---

## 5. Feuille de route suggérée (6 semaines)

1. **Semaine 1** — Pipeline Docling + fallback VLM local ; test sur échantillons réels.
2. **Semaine 2** — Schéma Pydantic canonique + parsing regex par type de document.
3. **Semaine 3** — Règles Pandera/Pydantic pour les cas métier RH.
4. **Semaine 4** — Détection PyOD (Isolation Forest/ECOD/COPOD) sur champs numériques.
5. **Semaine 5** — Dashboard Streamlit : upload → résultats → export.
6. **Semaine 6** — Tests d'intégration, cas limites, jeu de test étiqueté (20–30 documents synthétiques) pour rapporter la précision d'extraction séparément pour Docling et pour le fallback VLM.

---

*Ce document consolide et corrige les versions précédentes : le moteur d'extraction cloud (Gemini) a été remplacé par un VLM local pour rester cohérent avec le principe "les données ne quittent jamais l'hôte."*
