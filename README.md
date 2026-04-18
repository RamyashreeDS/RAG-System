# MediGuide — Local AI Health Companion

A Retrieval-Augmented Generation (RAG) system that transforms clinical hospital discharge summaries into clear, patient-friendly explanations — and answers everyday health questions. Runs 100% locally: no cloud, no data sharing.

## Features

- **Discharge Note Explainer** — Upload or paste a discharge note; MediGuide explains your diagnosis, medications, follow-up steps, and warning signs in plain English (6th-grade reading level)
- **Health Q&A** — Ask everyday health questions and get evidence-based home care advice, with clear guidance on when to see a doctor
- **Streaming responses** — Token-by-token output via Server-Sent Events (Ollama LLM or built-in fallback)
- **Hybrid RAG retrieval** — BM25 + PubMedBERT dense embeddings fused via Reciprocal Rank Fusion (RRF)
- **Conversation history** — Full chat history persisted in browser localStorage with one-click reload
- **Mode-specific recommendations** — Contextual follow-up question chips after every response
- **Input suggestions** — Dynamic question starters that update as you type
- **Spell correction** — Auto-detects 35+ common medical misspellings with one-click fix
- **File upload** — PDF, DOCX, TXT, PNG/JPG/TIFF/WEBP (OCR via Tesseract)
- **Dark / light mode** — CSS variable theming, fully responsive

---

## Architecture

| Component | Implementation |
|---|---|
| Section segmentation | Regex + clinical patterns (`preprocess.py`) |
| Entity normalisation | 80+ clinical abbreviation lookup + condition matcher |
| Medication extraction | Rule-based NER (`preprocess.py`) |
| Sparse retrieval | BM25Okapi (`rank_bm25`) |
| Dense retrieval | FAISS + PubMedBERT (`pritamdeka/S-PubMedBert-MS-MARCO`) |
| Fusion | Reciprocal Rank Fusion (RRF), weights BM25 0.45 / Dense 0.55 |
| Source filtering | Per-section allowed-source lists |
| Confidence threshold | Cosine similarity ≥ 0.28 |
| Generation | LLaMA 3.1 8B via Ollama (fully local) |
| Fallback | Template-based generation (no LLM required) |
| Output — Discharge | Diagnosis Explained · Your Medications · Follow-up Actions · Warning Signs |
| Output — Health Q&A | What This Could Be · Home Care Tips · When to See a Doctor · Go to the ER If |
| RAG provenance | Visible panel: every retrieved chunk with source, doc ID, BM25 / Dense / RRF scores |
| Retrieval eval | Precision@K, Recall@K, MRR |
| Generation eval | ROUGE-L, BERTScore, Flesch-Kincaid readability |
| Faithfulness | NLI classifier hook (`cross-encoder/nli-deberta-v3-base`) |

---

## Corpus — What's Actually Indexed

> **49,423 total chunks** from **~20,849 source documents** across 4 open datasets.

| Source | Raw Records | Chunks Indexed | Content |
|---|---|---|---|
| openFDA Drug Labels | 16,000 | 41,344 | FDA drug labels: indications, warnings, dosing, adverse reactions |
| MedlinePlus | ~1,100 topics | 3,634 | NIH plain-language health condition pages |
| PubMed Abstracts | 3,000 | 3,141 | Discharge-relevant clinical literature via NCBI Entrez |
| PLABA | 749 article pairs | 1,304 | PubMed abstracts paired with plain-language rewrites (75 clinical questions) |
| **Total** | **~20,849** | **49,423** | |

> **MIMIC-IV-Note** (331,794 clinical notes) is supported but requires credentialed PhysioNet access. Place files in `data/raw/mimic_notes/` to include them.

### Chunk settings
- Chunk size: 384 tokens · Overlap: 64 tokens
- Embedding model: `pritamdeka/S-PubMedBert-MS-MARCO`

---

## Quickstart

### Requirements
- Python 3.9+
- [Ollama](https://ollama.ai) (optional — a built-in fallback runs without it)
- Tesseract OCR (optional — only needed for image uploads)

```bash
pip install -r requirements.txt
```

### Step 1 — Download corpora

```bash
python scripts/download_open_corpora.py
```

Downloads MedlinePlus (~1,100 topics), openFDA (16,000 drug labels), PubMed (3,000 abstracts), and PLABA (749 pairs). Prints a corpus summary at the end.

### Step 2 — Build indexes

```bash
python scripts/build_indexes.py
```

Builds FAISS dense index + BM25 index. Takes ~10–20 minutes on first run.

### Step 3 — Start the web app

```bash
python run_app.py
```

Opens automatically at [http://localhost:8080](http://localhost:8080).

Optional flags:
```bash
python run_app.py --port 9000      # custom port
python run_app.py --no-browser     # headless / server mode
python run_app.py --reload         # hot-reload for development
```

### Step 4 — (Optional) Add Ollama LLM

```bash
ollama pull llama3.1:8b
ollama serve
```

Without Ollama, MediGuide uses its built-in template engine — still useful, just less fluent.

---

## CLI Demo

```bash
# Without Ollama (template fallback):
python scripts/run_demo.py --input data/sample_discharge_note.txt --no-ollama

# With Ollama:
python scripts/run_demo.py --input data/sample_discharge_note.txt

# Synthetic discharge notes:
python scripts/run_demo.py --input data/synthetic_notes/example_2.txt --no-ollama
python scripts/run_demo.py --input data/synthetic_notes/example_3.txt --no-ollama
```

The demo prints:
1. **Retrieved Evidence panel** — every chunk pulled from the RAG corpus with source name, doc ID, BM25 / Dense / RRF scores, and a text preview
2. **Patient-Facing Explanation** — the final 4-section output
3. **Preprocessing Summary** — sections detected, medications extracted, entities normalised

---

## Evaluation

```bash
python scripts/evaluate.py
```

Outputs Precision@5, Recall@5, MRR, ROUGE-L, Flesch-Kincaid grade to `outputs/evaluation.json`.

---

## Example RAG Provenance Output

```
======================================================================
  RETRIEVED EVIDENCE  —  Sources pulled from MediGuide corpus
======================================================================

▶ Section: DIAGNOSIS
  3 chunk(s) retrieved

  [1] Source: MedlinePlus (National Library of Medicine)
      Title:  Heart Failure
      Doc ID: medlineplus_42
      Scores: BM25=4.821  Dense=0.731  Fused(RRF)=0.0318
      Text preview: "Heart failure means your heart can't pump enough blood..."

  [2] Source: PubMed Biomedical Literature
      Title:  Heart failure with reduced ejection fraction: management
      Doc ID: pubmed_38291847
      Scores: BM25=3.104  Dense=0.689  Fused(RRF)=0.0291

▶ Section: MEDICATIONS
  3 chunk(s) retrieved

  [1] Source: FDA Drug Label Database
      Title:  FUROSEMIDE
      Doc ID: openfda_1847
      Scores: BM25=6.203  Dense=0.812  Fused(RRF)=0.0334
      Text preview: "Furosemide is a loop diuretic indicated for edema..."
----------------------------------------------------------------------
  Total chunks used: 9
  Breakdown:
    • FDA Drug Label Database: 41,344 chunks total
    • MedlinePlus (National Library of Medicine): 3,634 chunks total
    • PubMed Biomedical Literature: 3,141 chunks total
    • PLABA Plain-Language Biomedical Abstracts: 1,304 chunks total
======================================================================
```

---

## Project Structure

```
MediGuide/
├── app/
│   └── server.py              # FastAPI backend (SSE streaming, upload, health Q&A)
├── src/discharge_rag/
│   ├── config.py              # Paths, model settings, retrieval weights
│   ├── ingest.py              # Corpus loaders (MedlinePlus, openFDA, PubMed, PLABA)
│   ├── chunking.py            # Text chunking with overlap
│   ├── retrieval.py           # BM25 + FAISS + RRF fusion
│   ├── pipeline.py            # End-to-end RAG pipeline
│   ├── preprocess.py          # Section parsing, abbreviation expansion, med extraction
│   └── generation.py          # Prompts, fallback templates, HTML stripping
├── static/
│   ├── index.html             # Two-mode UI (Discharge Note + Health Q&A)
│   ├── app.js                 # SSE client, history, suggestions, spell correction
│   └── style.css              # CSS variables, dark mode, responsive layout
├── scripts/
│   ├── download_open_corpora.py
│   ├── build_indexes.py
│   ├── run_demo.py
│   └── evaluate.py
├── data/
│   ├── sample_discharge_note.txt
│   └── synthetic_notes/       # 4 synthetic discharge notes for testing
└── run_app.py                 # One-command launcher
```

---

## Troubleshooting

**"No corpora found"** — Run `python scripts/download_open_corpora.py` first.

**PLABA download fails** — Place `data.json` at `data/raw/plaba/data.json` (available at physionet.org/content/plaba-bionlp/).

**Ollama fails** — Use `--no-ollama` flag. Install Ollama and run `ollama pull llama3.1:8b` when ready.

**Image OCR not working** — Install Tesseract: `brew install tesseract` (macOS) or `apt install tesseract-ocr` (Linux).

**Port already in use** — Run `python run_app.py --port 8081` or `pkill -f uvicorn` to free port 8080.
