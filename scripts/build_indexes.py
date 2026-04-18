from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from discharge_rag.pipeline import DischargeRAGPipeline

if __name__ == "__main__":
    pipe = DischargeRAGPipeline()
    pipe.build_indexes()
    print("Indexes built.")
