# DischargeRAG — Full Proposal Architecture

A Retrieval-Augmented Generation system that transforms clinical discharge summaries into clear, patient-facing explanations.

## Architecture

| Component | Implementation |
|---|---|
| Section segmentation | Regex + clinical patterns (`preprocess.py`) |
| Entity normalization | 80+ clinical abbreviation lookup + condition matcher |
| Medication extraction | Rule-based NER (`preprocess.py`) |
| Sparse retrieval | BM25Okapi (`rank_bm25`) |
| Dense retrieval | FAISS + PubMedBERT (`pritamdeka/S-PubMedBert-MS-MARCO`) |
| Fusion | Reciprocal Rank Fusion (RRF) |
| Source filtering | Per-section allowed-source lists |
| Confidence threshold | Cosine similarity ≥ 0.28 |
| Generation | LLaMA 3.1 8B via Ollama (local) |
| Output format | 4 sections: Diagnosis Explained, Your Medications, Follow-up Actions, Warning Signs |
| RAG provenance | Visible panel showing every retrieved chunk, source, and retrieval scores |
| Retrieval eval | Precision@K, Recall@K, MRR |
| Generation eval | ROUGE-L, BERTScore, Flesch-Kincaid readability |
| Faithfulness | NLI classifier hook (cross-encoder/nli-deberta-v3-base) |

## Corpus  (10,000+ documents target)

| Source | Documents | What |
|---|---|---|
| MedlinePlus XML | ~1,100 | Plain-language health condition pages |
| openFDA Drug Labels | 8,000 | FDA drug labels (indications, warnings, dosing) |
| PubMed Abstracts | 1,000 | Discharge-relevant clinical literature via NCBI Entrez |
| PLABA | ~750 | PubMed abstract + plain-language rewrite pairs |
| **Total** | **~10,850** | **≥ 10,000 target ✓** |
| MIMIC-IV-Note | 331,794 | Credentialed — place files in `data/raw/mimic_notes/` |

## Install

```bash
pip install -r requirements.txt
```

## Step 1 — Download corpora (targets 10,000 docs)

```bash
python scripts/download_open_corpora.py
```

Downloads MedlinePlus (~1,100), openFDA (8,000), PubMed (1,000), and PLABA (~750).
Prints a corpus summary with total count at the end.

## Step 2 — Build indexes

```bash
python scripts/build_indexes.py
```

## Step 3 — Run demo

```bash
# Without Ollama (template fallback):
python scripts/run_demo.py --input data/sample_discharge_note.txt --no-ollama

# With Ollama (full LLM):
ollama pull llama3.1:8b && ollama serve
python scripts/run_demo.py --input data/sample_discharge_note.txt
```

The demo prints three panels:
1. **Retrieved Evidence panel** — every chunk pulled from the RAG corpus with source name, doc ID, BM25/Dense/RRF scores, and a text preview. Proves responses are grounded in your corpus, not LLM memory.
2. **Patient-Facing Explanation** — the final output.
3. **Preprocessing Summary** — sections detected, medications extracted, entities normalized.

Try the realistic synthetic notes:
```bash
python scripts/run_demo.py --input data/synthetic_notes/example_2.txt --no-ollama
python scripts/run_demo.py --input data/synthetic_notes/example_3.txt --no-ollama
python scripts/run_demo.py --input data/synthetic_notes/example_4.txt --no-ollama
```

## Step 4 — Evaluate

```bash
python scripts/evaluate.py
```

Outputs Precision@5, Recall@5, MRR, ROUGE-L, Flesch-Kincaid grade to `outputs/evaluation.json`.

## Example provenance output

```
======================================================================
  RETRIEVED EVIDENCE  —  Sources pulled from DischargeRAG corpus
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
      Text preview: "HFrEF is characterized by a left ventricular ejection..."

▶ Section: MEDICATIONS
  3 chunk(s) retrieved

  [1] Source: FDA Drug Label Database
      Title:  FUROSEMIDE
      Doc ID: openfda_1847
      Scores: BM25=6.203  Dense=0.812  Fused(RRF)=0.0334
      Text preview: "Furosemide is a loop diuretic indicated for edema..."
----------------------------------------------------------------------
  Total chunks used: 9
  Breakdown by corpus source:
    • MedlinePlus (National Library of Medicine): 4 chunk(s)
    • FDA Drug Label Database: 3 chunk(s)
    • PubMed Biomedical Literature: 2 chunk(s)
======================================================================
```

## Troubleshooting

**"No corpora found"** — Run `python scripts/download_open_corpora.py` first.

**PLABA auto-download fails** — Create a free PhysioNet account at physionet.org/content/plaba-bionlp/ and place the file at `data/raw/plaba/plaba.jsonl`.

**Ollama fails** — Use `--no-ollama` flag. Install Ollama and run `ollama pull llama3.1:8b` when ready.

**Want to suppress the provenance panel** — Pass `--no-provenance` to `run_demo.py`.
