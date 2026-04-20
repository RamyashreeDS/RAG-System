from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = ROOT / "indexes"
OUTPUT_DIR = ROOT / "outputs"

@dataclass
class RetrievalWeights:
    bm25: float = 0.45
    dense: float = 0.55

@dataclass
class Config:
    medlineplus_xml: Path = RAW_DIR / "medlineplus" / "medlineplus_topics.xml"
    openfda_jsonl: Path = RAW_DIR / "openfda" / "drug_labels.jsonl"
    plaba_jsonl: Path = RAW_DIR / "plaba" / "plaba.jsonl"
    plaba_json: Path = RAW_DIR / "plaba" / "data.json"
    pubmed_jsonl: Path = RAW_DIR / "pubmed" / "pubmed_abstracts.jsonl"
    mimic_notes_dir: Path = RAW_DIR / "mimic_notes"
    mimic_demo_dir: Path = RAW_DIR / "mimic_iv_demo"
    synthetic_notes_dir: Path = DATA_DIR / "synthetic_notes"

    chunk_size: int = 384
    chunk_overlap: int = 64
    top_k: int = 8
    similarity_threshold: float = 0.28
    index_dir: Path = INDEX_DIR / "default"
    retrieval_weights: RetrievalWeights = field(default_factory=RetrievalWeights)

    # Biomedical embedding model for better clinical semantic similarity.
    # Falls back to all-MiniLM-L6-v2 if the biomedical model is unavailable.
    embedding_model: str = "pritamdeka/S-PubMedBert-MS-MARCO"
    dense_model: str = "pritamdeka/S-PubMedBert-MS-MARCO"

    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

    use_section_filtering: bool = True
    use_source_filtering: bool = True

    valid_sources_for_section: Dict[str, List[str]] = field(default_factory=lambda: {
        "medications": ["openfda", "medlineplus"],
        "diagnosis": ["medlineplus", "plaba", "pubmed", "mimic_notes", "mimic_iv_demo"],
        "follow_up": ["medlineplus", "plaba", "pubmed", "mimic_notes", "mimic_iv_demo"],
        "warning_signs": ["medlineplus", "plaba", "pubmed", "mimic_notes", "mimic_iv_demo"],
        "general": ["medlineplus", "openfda", "plaba", "pubmed", "mimic_notes", "mimic_iv_demo"],
    })

    nli_model_name: Optional[str] = "cross-encoder/nli-deberta-v3-base"
    random_seed: int = 42

CFG = Config()
