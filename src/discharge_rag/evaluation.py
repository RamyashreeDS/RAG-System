from __future__ import annotations
from typing import Dict, List, Sequence
import numpy as np
from rouge_score import rouge_scorer
from bert_score import score as bertscore_score
import textstat
from transformers import pipeline

def precision_at_k(retrieved_ids: Sequence[str], gold_ids: Sequence[str], k: int) -> float:
    retrieved = list(retrieved_ids)[:k]
    if not retrieved:
        return 0.0
    hits = sum(1 for x in retrieved if x in set(gold_ids))
    return hits / k

def recall_at_k(retrieved_ids: Sequence[str], gold_ids: Sequence[str], k: int) -> float:
    gold = set(gold_ids)
    if not gold:
        return 0.0
    retrieved = set(list(retrieved_ids)[:k])
    return len(retrieved & gold) / len(gold)

def mean_reciprocal_rank(all_retrieved: List[Sequence[str]], all_gold: List[Sequence[str]]) -> float:
    rr = []
    for retrieved, gold in zip(all_retrieved, all_gold):
        gold_set = set(gold)
        rank = 0
        for i, rid in enumerate(retrieved, 1):
            if rid in gold_set:
                rank = i
                break
        rr.append(1.0 / rank if rank else 0.0)
    return float(np.mean(rr)) if rr else 0.0

def rouge_l(generated: str, reference: str) -> float:
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    return scorer.score(reference, generated)["rougeL"].fmeasure

def bertscore_f1(generated: List[str], reference: List[str]) -> float:
    P, R, F1 = bertscore_score(generated, reference, lang="en", verbose=False)
    return float(F1.mean().item())

def readability_grade(text: str) -> float:
    return float(textstat.flesch_kincaid_grade(text))

class FaithfulnessChecker:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name
        self.pipe = pipeline("text-classification", model=model_name) if model_name else None

    def contradiction_rate(self, claims: List[str], evidence: List[str]) -> float:
        if not self.pipe or not claims or not evidence:
            return 0.0
        contradictions = 0
        total = 0
        joined_evidence = " ".join(evidence)[:4000]
        for claim in claims:
            total += 1
            out = self.pipe({"text": joined_evidence, "text_pair": claim}, truncation=True)
            label = out[0]["label"].lower()
            if "contrad" in label:
                contradictions += 1
        return contradictions / total if total else 0.0
