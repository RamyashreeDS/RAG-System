from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import json
from discharge_rag.evaluation import precision_at_k, recall_at_k, mean_reciprocal_rank, rouge_l, readability_grade
from discharge_rag.pipeline import DischargeRAGPipeline

PLABA_JSON_PATH = ROOT / "data" / "raw" / "plaba" / "data.json"
PLABA_JSONL_PATH = ROOT / "data" / "raw" / "plaba" / "plaba.jsonl"
INDEX_PATH = ROOT / "indexes" / "default"


def _join_numbered_dict(d: dict) -> str:
    return " ".join(str(d[k]) for k in sorted(d.keys(), key=lambda x: int(x)))


def load_eval_rows(max_rows: int = 20):
    """Load evaluation rows from JSON (preferred) or JSONL fallback.

    Each row: {"doc_id": str, "source_text": str, "plain_language_text": str}
    """
    if PLABA_JSON_PATH.exists():
        rows = []
        data = json.loads(PLABA_JSON_PATH.read_text(encoding="utf-8"))
        for q_num, q_block in data.items():
            for pmid, article in q_block.items():
                if pmid in ("question", "question_type"):
                    continue
                abstract_dict = article.get("abstract", {})
                adaptations = article.get("adaptations", {})
                if not abstract_dict or not adaptations:
                    continue
                source_text = _join_numbered_dict(abstract_dict)
                first_adapt = next(iter(adaptations.values()), {})
                plain_text = _join_numbered_dict(first_adapt) if first_adapt else ""
                if source_text and plain_text:
                    rows.append({
                        "doc_id": f"plaba_{q_num}_{pmid}",
                        "source_text": source_text,
                        "plain_language_text": plain_text,
                    })
                if len(rows) >= max_rows:
                    return rows
        return rows

    if PLABA_JSONL_PATH.exists():
        rows = []
        with open(PLABA_JSONL_PATH, "r", encoding="utf-8") as f:
            for row_idx, line in enumerate(f):
                r = json.loads(line)
                src = r.get("source_text", "")
                plain = r.get("plain_language_text", "")
                if src and plain:
                    rows.append({
                        "doc_id": f"plaba_{row_idx}",
                        "source_text": src,
                        "plain_language_text": plain,
                    })
                if len(rows) >= max_rows:
                    break
        return rows

    return []


def main():
    if not INDEX_PATH.exists():
        print("[ERROR] Indexes not built yet.")
        print("  Run: python scripts/build_indexes.py")
        sys.exit(1)

    eval_rows = load_eval_rows(max_rows=20)
    if not eval_rows:
        print("[ERROR] No PLABA evaluation data found.")
        print(f"  Expected: {PLABA_JSON_PATH}  or  {PLABA_JSONL_PATH}")
        sys.exit(1)

    pipe = DischargeRAGPipeline()
    pipe.load_indexes()

    retrieval_runs = []
    gold_runs = []
    rouge_scores = []
    readability = []

    print(f"Evaluating on {len(eval_rows)} PLABA examples...")
    for i, row in enumerate(eval_rows):
        source_text = row["source_text"]
        plain = row["plain_language_text"]
        doc_id = row["doc_id"]
        result = pipe.explain(source_text, use_ollama=False)

        # Extract doc_ids from retrieved chunks — chunk dict is nested under "chunk" key
        retrieved_ids = []
        for sec in result["retrieved"].values():
            for item in sec[:3]:
                chunk = item.get("chunk", item)
                cid = chunk.get("doc_id", chunk.get("chunk_id", ""))
                if cid:
                    retrieved_ids.append(cid)

        retrieval_runs.append(retrieved_ids)
        gold_runs.append([doc_id])
        rouge_scores.append(rouge_l(result["output"], plain))
        readability.append(readability_grade(result["output"]))
        print(f"  [{i+1}/{len(eval_rows)}] ROUGE-L: {rouge_scores[-1]:.3f}  FK grade: {readability[-1]:.1f}")

    metrics = {
        "n_eval": len(eval_rows),
        "precision_at_5": sum(precision_at_k(r, g, 5) for r, g in zip(retrieval_runs, gold_runs)) / max(1, len(retrieval_runs)),
        "recall_at_5": sum(recall_at_k(r, g, 5) for r, g in zip(retrieval_runs, gold_runs)) / max(1, len(retrieval_runs)),
        "mrr": mean_reciprocal_rank(retrieval_runs, gold_runs),
        "avg_rouge_l": sum(rouge_scores) / max(1, len(rouge_scores)),
        "avg_fk_grade": sum(readability) / max(1, len(readability)),
    }
    out = ROOT / "outputs" / "evaluation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("\n=== Evaluation Results ===")
    print(json.dumps(metrics, indent=2))
    print(f"\nSaved: {out}")

if __name__ == "__main__":
    main()
