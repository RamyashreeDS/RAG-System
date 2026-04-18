from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import argparse
import json
from discharge_rag.pipeline import DischargeRAGPipeline
from discharge_rag.generation import format_provenance_panel

def main():
    parser = argparse.ArgumentParser(description="DischargeRAG demo")
    parser.add_argument("--input", type=str, default="data/sample_discharge_note.txt",
                        help="Path to discharge note (relative to project root)")
    parser.add_argument("--no-ollama", action="store_true",
                        help="Use template fallback instead of Ollama LLM")
    parser.add_argument("--no-provenance", action="store_true",
                        help="Hide the retrieved evidence panel")
    args = parser.parse_args()

    note_path = ROOT / args.input
    if not note_path.exists():
        print(f"[ERROR] Note not found: {note_path}")
        sys.exit(1)

    index_path = ROOT / "indexes" / "default"
    if not index_path.exists():
        print("[ERROR] Indexes not built yet. Run: python scripts/build_indexes.py")
        sys.exit(1)

    note_text = note_path.read_text(encoding="utf-8")

    print(f"\nLoading DischargeRAG pipeline...")
    pipe = DischargeRAGPipeline()
    pipe.load_indexes()
    print("Pipeline ready.\n")

    print("=" * 70)
    print("  INPUT: Discharge Note")
    print("=" * 70)
    print(note_text.strip())
    print()

    result = pipe.explain(note_text, use_ollama=not args.no_ollama)

    # ── Provenance panel ─────────────────────────────────────────────────────
    if not args.no_provenance:
        print()
        print(format_provenance_panel(result["retrieved"]))
        print()

    # ── Patient-facing output ─────────────────────────────────────────────────
    print("=" * 70)
    print("  OUTPUT: Patient-Facing Explanation")
    print("=" * 70)
    print(result["output"])

    # ── Preprocessing summary ─────────────────────────────────────────────────
    proc = result["processed"]
    print()
    print("=" * 70)
    print("  PREPROCESSING SUMMARY")
    print("=" * 70)
    print(f"  Sections detected:       {list(proc['sections'].keys())}")
    print(f"  Medications extracted:   {len(proc['medications'])}")
    for m in proc["medications"][:6]:
        print(f"    • {m.get('drug','')} {m.get('dose','')} {m.get('frequency','')}".strip())
    print(f"  Normalized entities:     {proc['normalized_terms']}")
    print()

    # ── Save full result ─────────────────────────────────────────────────────
    out = ROOT / "outputs" / "demo_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Full result saved to: {out}")

if __name__ == "__main__":
    main()
