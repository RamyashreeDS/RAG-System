from __future__ import annotations
import asyncio
import io
import json
import re
import sys
from pathlib import Path
from typing import AsyncGenerator, List

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discharge_rag.generation import SOURCE_LABELS, _strip_html, build_prompt, build_healthqa_prompt, fallback_template, healthqa_fallback
from discharge_rag.pipeline import DischargeRAGPipeline
from discharge_rag.preprocess import preprocess_note

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="MediGuide", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipe: DischargeRAGPipeline | None = None


def get_pipeline() -> DischargeRAGPipeline:
    global _pipe
    if _pipe is None:
        _pipe = DischargeRAGPipeline()
        _pipe.load_indexes()
    return _pipe


# ── Models ─────────────────────────────────────────────────────────────────────
class ExplainRequest(BaseModel):
    note_text: str
    use_ollama: bool = True


class HealthQARequest(BaseModel):
    question: str
    use_ollama: bool = True


# ── Helpers ────────────────────────────────────────────────────────────────────
def slim_retrieved(retrieved: dict) -> dict:
    out: dict = {}
    for section, items in retrieved.items():
        out[section] = []
        for item in items[:5]:
            chunk = item.get("chunk", item)
            src = chunk.get("source", "unknown")
            out[section].append({
                "source": src,
                "source_label": SOURCE_LABELS.get(src, src),
                "title": chunk.get("title", "")[:120],
                "text": _strip_html(chunk.get("text", ""))[:400],
                "bm25": round(item.get("bm25_score", 0.0), 3),
                "dense": round(item.get("dense_score", 0.0), 3),
                "fused": round(item.get("fused_score", 0.0), 4),
            })
    return out


async def stream_text(text: str, words_per_chunk: int = 4) -> AsyncGenerator[str, None]:
    words = text.split(" ")
    buf: List[str] = []
    for w in words:
        buf.append(w)
        if len(buf) >= words_per_chunk:
            yield " ".join(buf) + " "
            buf = []
            await asyncio.sleep(0.018)
    if buf:
        yield " ".join(buf)


async def stream_ollama(prompt: str, model: str, url: str) -> AsyncGenerator[str, None]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.15},
    }
    with requests.post(url, json=payload, stream=True, timeout=180) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                data = json.loads(line)
                tok = data.get("response", "")
                if tok:
                    yield tok
                if data.get("done"):
                    break


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    try:
        p = get_pipeline()
        return {
            "status": "ok",
            "chunks": len(p.retriever.chunks),
            "model": p.cfg.ollama_model,
            "index": str(p.cfg.index_dir),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/samples")
async def samples():
    notes = []
    sample_file = ROOT / "data" / "sample_discharge_note.txt"
    if sample_file.exists():
        notes.append({
            "title": "Sample Discharge Note",
            "subtitle": "General hospital discharge",
            "icon": "🏥",
            "text": sample_file.read_text(encoding="utf-8", errors="ignore")[:3000],
        })
    synth_dir = ROOT / "data" / "synthetic_notes"
    icons = ["❤️", "💉", "🫁", "🧠"]
    subtitles = ["Heart condition", "Diabetes management", "Respiratory care", "Neurology"]
    if synth_dir.exists():
        for i, f in enumerate(sorted(synth_dir.glob("*.txt"))[:4]):
            notes.append({
                "title": f.stem.replace("_", " ").title(),
                "subtitle": subtitles[i] if i < len(subtitles) else "Discharge note",
                "icon": icons[i] if i < len(icons) else "📋",
                "text": f.read_text(encoding="utf-8", errors="ignore")[:3000],
            })
    return notes


def _extract_text(content: bytes, filename: str) -> str:
    """Extract plain text from uploaded file regardless of format."""
    name = (filename or "").lower()
    ext  = Path(name).suffix

    # ── Plain text ────────────────────────────────────────────────────────────
    if ext in (".txt", ".text", ""):
        return content.decode("utf-8", errors="ignore")

    # ── PDF ───────────────────────────────────────────────────────────────────
    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages).strip()
            if text:
                return text
        except Exception:
            pass
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(p.extract_text() or "" for p in reader.pages).strip()
        except Exception as e:
            raise HTTPException(422, f"Could not read PDF: {e}")

    # ── Word documents ────────────────────────────────────────────────────────
    if ext in (".docx",):
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise HTTPException(422, f"Could not read DOCX: {e}")

    if ext in (".doc",):
        raise HTTPException(422, "Legacy .doc format is not supported. Please save as .docx or .pdf and re-upload.")

    # ── Images (OCR) ─────────────────────────────────────────────────────────
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"):
        try:
            import pytesseract
            from PIL import Image
            img  = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(img, lang="eng").strip()
            if not text:
                raise HTTPException(422, "No text could be read from the image. Make sure the discharge note is clearly visible and not blurry.")
            return text
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(422, f"Image OCR failed: {e}")

    raise HTTPException(415, f"Unsupported file type '{ext}'. Supported: PDF, DOCX, TXT, PNG, JPG, JPEG, TIFF, WEBP.")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty.")
    try:
        text = _extract_text(content, file.filename or "")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Unexpected error reading file: {e}")

    if not text.strip():
        raise HTTPException(422, "No readable text found in the file.")

    return {"text": text.strip(), "filename": file.filename, "chars": len(text)}


@app.post("/api/explain")
async def explain(req: ExplainRequest):
    if not req.note_text.strip():
        raise HTTPException(400, "Empty note text")

    p = get_pipeline()

    async def generate() -> AsyncGenerator[str, None]:
        def sse(event: str, data) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            yield sse("status", {"text": "Reading your discharge note…", "step": 1})
            processed = preprocess_note(req.note_text)
            await asyncio.sleep(0.05)

            yield sse("status", {"text": "Searching medical knowledge base…", "step": 2})
            retrieved = p.retrieve_for_note(req.note_text)
            yield sse("sources", slim_retrieved(retrieved))
            await asyncio.sleep(0.05)

            yield sse("status", {"text": "Preparing your personalised explanation…", "step": 3})
            prompt = build_prompt(req.note_text, retrieved)

            full = ""
            ollama_ok = False

            if req.use_ollama:
                try:
                    async for tok in stream_ollama(prompt, p.cfg.ollama_model, p.cfg.ollama_url):
                        full += tok
                        yield sse("token", {"text": tok})
                    ollama_ok = bool(full.strip())
                except Exception:
                    full = ""
                    yield sse("status", {"text": "Using built-in explanation engine…", "step": 3})

            if not ollama_ok:
                tmpl = fallback_template(
                    req.note_text,
                    processed.medications,
                    processed.normalized_terms,
                    retrieved,
                    sections=processed.sections,
                )
                async for chunk in stream_text(tmpl):
                    full += chunk
                    yield sse("token", {"text": chunk})

            yield sse("done", {
                "medications": processed.medications[:8],
                "diagnoses": processed.normalized_terms[:6],
            })

        except Exception as e:
            yield sse("error", {"text": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/healthqa")
async def healthqa(req: HealthQARequest):
    if not req.question.strip():
        raise HTTPException(400, "Empty question")

    p = get_pipeline()

    async def generate() -> AsyncGenerator[str, None]:
        def sse(event: str, data) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            yield sse("status", {"text": "Searching medical knowledge base…", "step": 1})
            retrieved = p.retrieve_for_note(req.question)
            yield sse("sources", slim_retrieved(retrieved))
            await asyncio.sleep(0.05)

            yield sse("status", {"text": "Preparing your answer…", "step": 2})
            prompt = build_healthqa_prompt(req.question, retrieved)

            full = ""
            ollama_ok = False

            if req.use_ollama:
                try:
                    async for tok in stream_ollama(prompt, p.cfg.ollama_model, p.cfg.ollama_url):
                        full += tok
                        yield sse("token", {"text": tok})
                    ollama_ok = bool(full.strip())
                except Exception:
                    full = ""
                    yield sse("status", {"text": "Using built-in answer engine…", "step": 2})

            if not ollama_ok:
                tmpl = healthqa_fallback(req.question, retrieved)
                async for chunk in stream_text(tmpl):
                    full += chunk
                    yield sse("token", {"text": chunk})

            yield sse("done", {})

        except Exception as e:
            yield sse("error", {"text": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Static files ───────────────────────────────────────────────────────────────
STATIC = ROOT / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC / "index.html"))
