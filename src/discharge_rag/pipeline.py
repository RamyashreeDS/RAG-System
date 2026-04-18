from __future__ import annotations
from pathlib import Path
from typing import Dict, List
import json

from .config import CFG
from .preprocess import preprocess_note
from .ingest import load_all_corpora
from .chunking import chunk_sectioned_doc
from .retrieval import HybridRetriever
from .generation import build_prompt, call_ollama, fallback_template

class DischargeRAGPipeline:
    def __init__(self, cfg=CFG):
        self.cfg = cfg
        self.retriever = HybridRetriever(cfg.dense_model)

    def build_indexes(self) -> None:
        docs = load_all_corpora(
            self.cfg.medlineplus_xml,
            self.cfg.openfda_jsonl,
            self.cfg.plaba_jsonl,
            self.cfg.mimic_notes_dir,
            self.cfg.pubmed_jsonl,
            self.cfg.mimic_demo_dir,
            self.cfg.plaba_json,
        )
        if not docs:
            raise FileNotFoundError("No corpora found. Download open corpora or add local files.")
        enriched = []
        for doc in docs:
            processed = preprocess_note(doc["text"])
            doc["sections"] = processed.sections
            enriched.append(doc)
        chunks = []
        for doc in enriched:
            chunks.extend(chunk_sectioned_doc(doc, self.cfg.chunk_size, self.cfg.chunk_overlap))
        self.retriever.fit(chunks)
        self.retriever.save(self.cfg.index_dir)

    def load_indexes(self, path: Path | None = None) -> None:
        p = path or self.cfg.index_dir
        self.retriever.load(p)

    def retrieve_for_note(self, note_text: str) -> Dict[str, List[Dict]]:
        processed = preprocess_note(note_text)
        queries = {
            "diagnosis": " ".join([processed.sections.get("diagnosis", ""), " ".join(processed.normalized_terms)]).strip() or processed.cleaned_text[:500],
            "medications": processed.sections.get("medications", "") or " ".join(m["drug"] for m in processed.medications),
            "follow_up": processed.sections.get("follow_up", "") or processed.cleaned_text[:400],
            "warning_signs": processed.sections.get("warning_signs", "") or processed.cleaned_text[:400],
        }
        outputs = {}
        for section, query in queries.items():
            allowed_sources = self.cfg.valid_sources_for_section.get(section, self.cfg.valid_sources_for_section["general"])
            results = self.retriever.search(
                query=query or processed.cleaned_text[:400],
                top_k=self.cfg.top_k,
                section=section if self.cfg.use_section_filtering else "general",
                allowed_sources=allowed_sources if self.cfg.use_source_filtering else None,
                similarity_threshold=self.cfg.similarity_threshold,
            )
            outputs[section] = [
                {
                    "chunk": r.chunk,
                    "bm25_score": r.bm25_score,
                    "dense_score": r.dense_score,
                    "fused_score": r.fused_score,
                }
                for r in results
            ]
        return outputs

    def explain(self, note_text: str, use_ollama: bool = True) -> Dict:
        processed = preprocess_note(note_text)
        retrieved = self.retrieve_for_note(note_text)
        prompt = build_prompt(note_text, retrieved)
        generation = None
        if use_ollama:
            try:
                generation = call_ollama(prompt, self.cfg.ollama_model, self.cfg.ollama_url)
            except Exception:
                generation = None
        if not generation:
            generation = fallback_template(note_text, processed.medications, processed.normalized_terms, retrieved)
        return {
            "processed": {
                "sections": processed.sections,
                "medications": processed.medications,
                "normalized_terms": processed.normalized_terms,
            },
            "retrieved": retrieved,
            "output": generation,
        }
