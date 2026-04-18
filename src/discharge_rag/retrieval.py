from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import math
import pickle
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

@dataclass
class RetrievedChunk:
    chunk: Dict
    bm25_score: float
    dense_score: float
    fused_score: float

class HybridRetriever:
    def __init__(self, embedding_model: str):
        self.model = SentenceTransformer(embedding_model)
        self.bm25 = None
        self.chunks: List[Dict] = []
        self.corpus_tokens: List[List[str]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.index = None

    def fit(self, chunks: List[Dict]) -> None:
        self.chunks = chunks
        self.corpus_tokens = [c["text"].lower().split() for c in chunks]
        self.bm25 = BM25Okapi(self.corpus_tokens)
        self.embeddings = self.model.encode(
            [c["text"] for c in chunks],
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")
        dim = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(self.embeddings)

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "chunks.pkl", "wb") as f:
            pickle.dump(self.chunks, f)
        with open(path / "bm25.pkl", "wb") as f:
            pickle.dump(self.bm25, f)
        np.save(path / "embeddings.npy", self.embeddings)
        faiss.write_index(self.index, str(path / "faiss.index"))

    def load(self, path: Path) -> None:
        with open(path / "chunks.pkl", "rb") as f:
            self.chunks = pickle.load(f)
        with open(path / "bm25.pkl", "rb") as f:
            self.bm25 = pickle.load(f)
        self.embeddings = np.load(path / "embeddings.npy").astype("float32")
        self.index = faiss.read_index(str(path / "faiss.index"))

    def _rrf(self, rankings: List[List[int]], k: int = 60) -> Dict[int, float]:
        scores: Dict[int, float] = {}
        for ranking in rankings:
            for rank, idx in enumerate(ranking, 1):
                scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
        return scores

    def search(
        self,
        query: str,
        top_k: int = 8,
        section: str = "general",
        allowed_sources: Optional[List[str]] = None,
        similarity_threshold: float = 0.28,
    ) -> List[RetrievedChunk]:
        if not self.chunks:
            raise ValueError("Retriever has not been fit or loaded.")

        q_tokens = query.lower().split()
        bm25_scores = self.bm25.get_scores(q_tokens)
        q_emb = self.model.encode([query], normalize_embeddings=True, show_progress_bar=False).astype("float32")
        dense_scores, dense_idx = self.index.search(q_emb, min(top_k * 8, len(self.chunks)))
        dense_scores = dense_scores[0]
        dense_idx = dense_idx[0]

        bm25_ranking = np.argsort(-bm25_scores)[: min(top_k * 8, len(self.chunks))].tolist()
        dense_ranking = dense_idx.tolist()
        rrf_scores = self._rrf([bm25_ranking, dense_ranking])

        candidates = set(bm25_ranking) | set(dense_ranking)
        results = []
        for idx in candidates:
            chunk = self.chunks[idx]
            if allowed_sources and chunk.get("source") not in allowed_sources:
                continue
            if section != "general":
                # hard prefer same section; still allow general
                if chunk.get("section") not in {section, "general"}:
                    continue
            d_score = float(np.dot(q_emb[0], self.embeddings[idx]))
            if d_score < similarity_threshold:
                continue
            results.append(RetrievedChunk(
                chunk=chunk,
                bm25_score=float(bm25_scores[idx]),
                dense_score=d_score,
                fused_score=float(rrf_scores.get(idx, 0.0)),
            ))
        results.sort(key=lambda x: (-x.fused_score, -x.dense_score, -x.bm25_score))
        return results[:top_k]
