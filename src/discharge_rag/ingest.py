from __future__ import annotations
from pathlib import Path
from typing import Dict, Iterable, List
import json
import pandas as pd
from lxml import etree


def _local_name(tag: str) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""

def _doc(doc_id: str, text: str, source: str, title: str = "", metadata: Dict | None = None) -> Dict:
    return {
        "id": doc_id,
        "title": title,
        "text": text,
        "source": source,
        "metadata": metadata or {},
    }

def load_medlineplus(xml_path: Path) -> List[Dict]:
    if not xml_path.exists():
        return []
    docs = []
    parser = etree.XMLParser(recover=True, huge_tree=True)
    root = etree.parse(str(xml_path), parser=parser).getroot()
    topics = [elem for elem in root.iter() if _local_name(getattr(elem, "tag", "")) == "health-topic"]

    for i, topic in enumerate(topics):
        title = ""
        for child in topic.iter():
            if _local_name(getattr(child, "tag", "")) == "title":
                title = " ".join(" ".join(child.itertext()).split())
                if title:
                    break
        full = " ".join(" ".join(topic.itertext()).split())
        if full:
            docs.append(_doc(f"medlineplus_{i}", full, "medlineplus", title=title))
    return docs

def load_openfda(jsonl_path: Path) -> List[Dict]:
    if not jsonl_path.exists():
        return []
    docs = []
    with open(jsonl_path, "r", encoding="utf-8") as reader:
        for i, line in enumerate(reader):
            row = json.loads(line)
            openfda = row.get("openfda", {})
            title = ", ".join(openfda.get("brand_name", [])[:2]) or ", ".join(openfda.get("generic_name", [])[:2]) or f"drug_{i}"
            parts = []
            for k in ["indications_and_usage", "dosage_and_administration", "warnings", "adverse_reactions"]:
                value = row.get(k, [])
                if isinstance(value, list):
                    parts.extend(value[:2])
            text = "\n".join(parts).strip()
            if text:
                docs.append(_doc(f"openfda_{i}", text, "openfda", title=title, metadata={"openfda": openfda}))
    return docs

def load_plaba(jsonl_path: Path) -> List[Dict]:
    if not jsonl_path.exists():
        return []
    docs = []
    with open(jsonl_path, "r", encoding="utf-8") as reader:
        for i, line in enumerate(reader):
            row = json.loads(line)
            q = row.get("question", "")
            src = row.get("source_text", "")
            tgt = row.get("plain_language_text", "")
            text = f"QUESTION: {q}\nSOURCE: {src}\nPLAIN_LANGUAGE: {tgt}".strip()
            if text:
                docs.append(_doc(f"plaba_{i}", text, "plaba", title=q[:120], metadata=row))
    return docs


def _join_numbered_dict(d: dict) -> str:
    return " ".join(str(d[k]) for k in sorted(d.keys(), key=lambda x: int(x)))


def load_plaba_json(json_path: Path) -> List[Dict]:
    """Load PLABA data.json (nested format: question -> PMID -> abstract/adaptations)."""
    if not json_path.exists():
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    docs = []
    for q_num, q_block in data.items():
        question = q_block.get("question", "")
        for pmid, article in q_block.items():
            if pmid in ("question", "question_type"):
                continue
            title = article.get("Title", "")
            abstract_dict = article.get("abstract", {})
            adaptations = article.get("adaptations", {})
            if not abstract_dict or not adaptations:
                continue
            abstract_text = _join_numbered_dict(abstract_dict)
            first_adapt = next(iter(adaptations.values()), {})
            plain_text = _join_numbered_dict(first_adapt) if first_adapt else ""
            if not abstract_text or not plain_text:
                continue
            text = f"QUESTION: {question}\nSOURCE: {abstract_text}\nPLAIN_LANGUAGE: {plain_text}"
            doc_id = f"plaba_{q_num}_{pmid}"
            docs.append(_doc(doc_id, text, "plaba", title=title or question[:120], metadata={
                "question": question,
                "pmid": pmid,
                "q_num": q_num,
            }))
    return docs

def load_mimic_notes(notes_dir: Path, source: str = "mimic_notes") -> List[Dict]:
    docs = []
    if not notes_dir.exists():
        return docs
    for file in notes_dir.iterdir():
        if file.suffix.lower() == ".txt":
            txt = file.read_text(encoding="utf-8", errors="ignore")
            docs.append(_doc(file.stem, txt, source, title=file.stem))
        elif file.suffix.lower() == ".csv":
            df = pd.read_csv(file)
            text_col = next((c for c in df.columns if c.lower() in {"text", "note_text", "discharge_summary"}), None)
            if text_col:
                for idx, row in df.iterrows():
                    docs.append(_doc(f"{file.stem}_{idx}", str(row[text_col]), source, title=str(row.get("subject_id", file.stem)), metadata=row.to_dict()))
        elif file.suffix.lower() == ".jsonl":
            with open(file, "r", encoding="utf-8") as reader:
                for idx, line in enumerate(reader):
                    row = json.loads(line)
                    text = row.get("text") or row.get("note_text") or row.get("discharge_summary")
                    if text:
                        docs.append(_doc(f"{file.stem}_{idx}", text, source, title=str(row.get("subject_id", file.stem)), metadata=row))
    return docs

def load_pubmed(jsonl_path: Path) -> List[Dict]:
    if not jsonl_path.exists():
        return []
    docs = []
    with open(jsonl_path, "r", encoding="utf-8") as reader:
        for i, line in enumerate(reader):
            row = json.loads(line)
            title = row.get("title", f"pubmed_{i}")
            abstract = row.get("abstract", "")
            if abstract:
                docs.append(_doc(
                    f"pubmed_{row.get('pmid', i)}",
                    f"{title}\n{abstract}",
                    "pubmed",
                    title=title,
                    metadata={"pmid": row.get("pmid", "")},
                ))
    return docs


def load_all_corpora(
    medlineplus_xml: Path,
    openfda_jsonl: Path,
    plaba_jsonl: Path,
    mimic_notes_dir: Path,
    pubmed_jsonl: Path | None = None,
    mimic_demo_dir: Path | None = None,
    plaba_json: Path | None = None,
) -> List[Dict]:
    docs = []
    docs.extend(load_medlineplus(medlineplus_xml))
    docs.extend(load_openfda(openfda_jsonl))
    if plaba_json is not None and plaba_json.exists():
        docs.extend(load_plaba_json(plaba_json))
    else:
        docs.extend(load_plaba(plaba_jsonl))
    docs.extend(load_mimic_notes(mimic_notes_dir))
    if pubmed_jsonl is not None:
        docs.extend(load_pubmed(pubmed_jsonl))
    if mimic_demo_dir is not None:
        docs.extend(load_mimic_notes(mimic_demo_dir, source="mimic_iv_demo"))
    return docs
