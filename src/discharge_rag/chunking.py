from __future__ import annotations
from typing import Dict, List

def _tokenize(text: str) -> List[str]:
    return text.split()

def chunk_text(text: str, chunk_size: int = 384, overlap: int = 64) -> List[str]:
    tokens = _tokenize(text)
    if not tokens:
        return []
    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(tokens), step):
        chunk = tokens[i:i + chunk_size]
        if chunk:
            chunks.append(" ".join(chunk))
        if i + chunk_size >= len(tokens):
            break
    return chunks

def chunk_sectioned_doc(doc: Dict, chunk_size: int = 384, overlap: int = 64) -> List[Dict]:
    text = doc["text"]
    sections = doc.get("sections", {"general": text})
    chunks = []
    counter = 0
    for section_name, section_text in sections.items():
        for piece in chunk_text(section_text, chunk_size=chunk_size, overlap=overlap):
            chunks.append({
                "chunk_id": f"{doc['id']}_chunk_{counter}",
                "doc_id": doc["id"],
                "title": doc.get("title", ""),
                "text": piece,
                "source": doc.get("source", "unknown"),
                "section": section_name,
                "metadata": doc.get("metadata", {}),
            })
            counter += 1
    return chunks
