from __future__ import annotations
from typing import Dict, List
import re
import textwrap
import requests

SYSTEM_PROMPT = """You are MediGuide, a warm and caring health companion helping patients understand their hospital discharge paperwork.

Speak directly to the patient using "you" and "your". Write like a trusted friend who is also a doctor — clear, kind, and reassuring.

Rules:
1. Use ONLY facts from the retrieved context below. Never invent information.
2. Explain every medical term in plain English right after you use it, e.g. "atrial fibrillation (an irregular heartbeat)".
3. Write at a 6th-grade reading level. Short sentences. Simple words.
4. Be warm and encouraging, but honest about serious symptoms.
5. Format your response with exactly these four markdown sections:

## 🔍 Diagnosis Explained
## 💊 Your Medications
## 📅 Follow-up Instructions
## 🚨 Warning Signs

6. For each medication: what it is, what it does, how to take it, and one key thing to watch for.
7. If something is not in the retrieved context, say: "I don't have specific details about this — please ask your care team."
8. End each section with one brief, encouraging sentence.
"""

FOLLOWUP_SYSTEM_PROMPT = """You are MediGuide, a warm and caring health companion.

A patient has asked a follow-up question regarding their hospital discharge note.
Speak directly to the patient using "you" and "your". Write like a trusted friend who is also a doctor — clear, kind, and reassuring.

Rules:
1. Use ONLY facts from the retrieved context below, or from the provided discharge note. Never invent medical advice.
2. Answer their specific question directly.
3. Format your response with exactly these three markdown sections:

## 💡 Direct Answer
## 📝 Practical Advice
## 🩺 Medical Guidance

4. Write at a 6th-grade reading level. Short sentences. Simple words.
5. If the answer is not in the context, say: "I don't have specific details about this — please ask your care team."
"""

SOURCE_LABELS = {
    "medlineplus": "MedlinePlus (National Library of Medicine)",
    "openfda":     "FDA Drug Label Database",
    "plaba":       "PLABA Plain-Language Biomedical Abstracts",
    "pubmed":      "PubMed Biomedical Literature",
    "mimic_notes": "Clinical Notes (MIMIC-IV)",
    "mimic_iv_demo": "Clinical Notes (MIMIC-IV Demo)",
}


def format_provenance_panel(retrieved: Dict[str, List[Dict]]) -> str:
    """
    Build a human-readable panel showing exactly which RAG chunks
    were retrieved and which source they came from — proving the
    response is grounded in our corpus, not the LLM's parametric memory.
    """
    lines = [
        "=" * 70,
        "  RETRIEVED EVIDENCE  —  Sources pulled from DischargeRAG corpus",
        "=" * 70,
    ]

    total_chunks = 0
    source_counts: Dict[str, int] = {}

    for section, items in retrieved.items():
        if not items:
            continue
        lines.extend([
            f"\n▶ Section: {section.upper().replace('_', ' ')}",
            f"  {len(items)} chunk(s) retrieved",
            "",
        ])
        for i, item in enumerate(items, 1):
            chunk = item.get("chunk", item)
            source = chunk.get("source", "unknown")
            source_label = SOURCE_LABELS.get(source, source)
            doc_id = chunk.get("doc_id", chunk.get("chunk_id", "?"))
            title = chunk.get("title", "")
            text = chunk.get("text", "")
            bm25 = item.get("bm25_score", 0.0)
            dense = item.get("dense_score", 0.0)
            fused = item.get("fused_score", 0.0)

            # Truncate text preview to 200 chars
            preview = text[:200].replace("\n", " ") + ("..." if len(text) > 200 else "")

            entry = [f"  [{i}] Source: {source_label}"]
            if title:
                entry.append(f"      Title:  {title[:80]}")
            entry.extend([
                f"      Doc ID: {doc_id}",
                f"      Scores: BM25={bm25:.3f}  Dense={dense:.3f}  Fused(RRF)={fused:.4f}",
                f"      Text preview: \"{preview}\"",
                "",
            ])
            lines.extend(entry)

            source_counts[source] = source_counts.get(source, 0) + 1
            total_chunks += 1

    lines.extend(["-" * 70, f"  Total chunks used: {total_chunks}", "  Breakdown by corpus source:"])
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        label = SOURCE_LABELS.get(source, source)
        lines.append(f"    • {label}: {count} chunk(s)")
    lines.append("=" * 70)
    return "\n".join(lines)


def build_prompt(note_text: str, retrieved: Dict[str, List[Dict]]) -> str:
    is_followup = "\n\n--- Follow-up question:" in note_text
    blocks = []
    for section, items in retrieved.items():
        if not items:
            continue
        blocks.append(f"## Retrieved evidence for {section.upper().replace('_', ' ')}")
        for i, item in enumerate(items, 1):
            chunk = item.get("chunk", item)
            source = chunk.get("source", "unknown")
            source_label = SOURCE_LABELS.get(source, source)
            title = chunk.get("title", "")
            text = chunk.get("text", "")
            header = f"[{section.upper()} #{i} | Source: {source_label}"
            if title:
                header += f" | Title: {title[:60]}"
            header += "]"
            blocks.append(f"{header}\n{text}")
    evidence = "\n\n".join(blocks)

    if is_followup:
        parts = note_text.split("\n\n--- Follow-up question:")
        original_note = parts[0].strip()
        question = parts[1].strip()
        return f"""{FOLLOWUP_SYSTEM_PROMPT}

Original discharge note context:
{original_note}

Retrieved medical evidence:
{evidence}

Patient's follow-up question: {question}

Answer the patient's question now directly in a conversational tone. Do not use '##' section headers.
"""

    return f"""{SYSTEM_PROMPT}

Original discharge note:
{note_text}

Retrieved context from DischargeRAG corpus:
{evidence}

Write the patient-facing explanation now. Every claim must come from the retrieved context above.
"""


def call_ollama(prompt: str, model: str, url: str) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common entities from corpus text."""
    text = re.sub(r'<[^>]+>', ' ', text)
    for ent, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                      ('&quot;', '"'), ('&nbsp;', ' '), ('&#39;', "'")]:
        text = text.replace(ent, char)
    text = re.sub(r'&[a-zA-Z]+;|&#\d+;', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _sentence_clip(text: str, max_chars: int = 500) -> str:
    """Clip to max_chars at the nearest sentence boundary — no trailing ellipsis."""
    if len(text) <= max_chars:
        return text
    sub = text[:max_chars]
    for punct in ['. ', '! ', '? ']:
        idx = sub.rfind(punct)
        if idx >= max_chars // 3:
            return sub[:idx + 1].strip()
    idx = sub.rfind(' ')
    return (sub[:idx] if idx > 0 else sub).rstrip(' .,;:') + '.'


def fallback_template(
    note_text: str,
    medications: List[Dict],
    diagnoses: List[str],
    retrieved: Dict[str, List[Dict]],
    sections: Dict[str, str] | None = None,
) -> str:
    """Template-based generation used when Ollama is unavailable."""
    is_followup = "\n\n--- Follow-up question:" in note_text
    if is_followup:
        question = note_text.split("\n\n--- Follow-up question:")[-1].strip()
        return f"Regarding your follow-up question about: '{question}'...\n\n(Note: The AI processing server is currently offline or unreachable. A personalized natural language answer cannot be generated right now. Please refer to your paperwork directly!)"

    # Patient-facing sources only — avoids dumping raw research abstracts
    PATIENT_SOURCES = {"medlineplus", "openfda"}

    def _patient_chunks(section: str, n: int = 3) -> List[str]:
        """Return bullet lines from MedlinePlus/FDA chunks only."""
        items = retrieved.get(section, [])
        out = []
        for item in items:
            chunk = item.get("chunk", item)
            if chunk.get("source") not in PATIENT_SOURCES:
                continue
            text = _strip_html(chunk.get("text", "").replace("\n", " "))
            # Skip PLABA-style QUESTION:/SOURCE: blocks
            if text.startswith("QUESTION:") or text.startswith("SOURCE:"):
                continue
            text = _sentence_clip(text, 420)
            if text:
                out.append(f"  • {text}")
            if len(out) >= n:
                break
        return out

    # ── Medications ── prefer raw section lines over regex-extracted dict ─────
    med_section_raw = (sections or {}).get("medications", "")
    if med_section_raw:
        med_lines = []
        for line in med_section_raw.splitlines():
            line = line.strip()
            if not line or len(line) < 5:
                continue
            # Skip bare section-header lines that slipped through
            if re.match(r'^discharge medications?[:\s]*$', line, re.IGNORECASE):
                continue
            med_lines.append(f"  • {line}")
        meds_text = "\n".join(med_lines[:10]) or "  • Please refer to the medication list in your discharge papers."
    else:
        meds_text = "\n".join(
            f"  • **{m.get('drug', '')}** {m.get('dose', '')} {m.get('frequency', '')}".strip()
            for m in medications[:8]
            if m.get("drug") and len(m.get("drug", "")) > 3
        ) or "  • Please refer to the medication list in your discharge papers."

    # ── Diagnosis ─────────────────────────────────────────────────────────────
    diag_text = ", ".join(diagnoses[:5]) if diagnoses else "the conditions described in your discharge note"
    diag_extra = _patient_chunks("diagnosis", n=2)
    diag_detail = ("\n" + "\n".join(diag_extra)) if diag_extra else ""

    # ── Follow-up — prefer text extracted directly from the note ──────────────
    note_followup = (sections or {}).get("follow_up", "").strip()
    if note_followup:
        follow_lines = [f"  • {line.strip()}" for line in note_followup.splitlines() if line.strip()][:6]
    else:
        follow_lines = _patient_chunks("follow_up", n=3) or [
            "  • Schedule a follow-up appointment with your doctor within 1–2 weeks.",
            "  • Bring all your medications to your next appointment.",
            "  • Contact your care team if you have any questions.",
        ]

    # ── Warning signs — prefer text extracted directly from the note ──────────
    note_warnings = (sections or {}).get("warning_signs", "").strip()
    if note_warnings:
        warning_lines = [f"  • {line.strip()}" for line in note_warnings.splitlines() if line.strip()][:6]
    else:
        warning_lines = _patient_chunks("warning_signs", n=3) or [
            "  • Chest pain or pressure",
            "  • Difficulty breathing or shortness of breath",
            "  • Sudden confusion or dizziness",
            "  • High fever (over 101°F / 38.3°C)",
            "  • Any symptom that worries you or feels severe",
        ]

    return f"""## 🔍 Diagnosis Explained
You were treated for {diag_text}. Your medical team worked to stabilise these conditions before you went home.{diag_detail}
You're on your way to recovery — understanding your diagnosis is the first step.

## 💊 Your Medications
Here are the medications from your discharge note. Take each one exactly as directed and do not stop without talking to your doctor first.
{meds_text}
If you have any questions about a medication, your pharmacist is a great free resource.

## 📅 Follow-up Actions
These are your next steps after leaving the hospital:
{chr(10).join(follow_lines)}
Keeping your follow-up appointments is one of the most important things you can do for your recovery.

## ⚠️ Warning Signs
Go to the emergency room or call your doctor right away if you notice any of these:
{chr(10).join(warning_lines)}
Trust your instincts — if something feels wrong, it is always okay to seek help immediately.
"""


HEALTHQA_SYSTEM_PROMPT = """You are MediGuide's everyday health companion. Patients come to you with day-to-day health questions.

Speak directly to the patient using "you" and "your". Be warm, calm, and reassuring — like a knowledgeable friend.

Rules:
1. Use ONLY facts from the retrieved context below. Never invent information.
2. Explain every medical term in plain English right after you use it.
3. Write at a 6th-grade reading level. Short sentences. Simple words.
4. NEVER diagnose — say "this could be" or "common causes include".
5. Format your response with exactly these four markdown sections:

## 🤔 What This Could Be
## 🏠 Home Care Tips
## 🩺 When to See a Doctor
## 🚨 Go to the ER If

6. For home care tips: be specific and practical (e.g. "drink 8 glasses of water daily").
7. If something is not in the retrieved context, say: "I don't have specific details about this — please ask your healthcare provider."
8. End each section with one brief, encouraging sentence.
"""


def build_healthqa_prompt(question: str, retrieved: Dict[str, List[Dict]]) -> str:
    blocks = []
    for section, items in retrieved.items():
        if not items:
            continue
        blocks.append(f"## Retrieved evidence for {section.upper().replace('_', ' ')}")
        for i, item in enumerate(items[:3], 1):
            chunk = item.get("chunk", item)
            source = chunk.get("source", "unknown")
            source_label = SOURCE_LABELS.get(source, source)
            text = chunk.get("text", "")
            title = chunk.get("title", "")
            header = f"[#{i} | {source_label}"
            if title:
                header += f" | {title[:60]}"
            header += "]"
            blocks.append(f"{header}\n{text}")
    evidence = "\n\n".join(blocks)
    return f"""{HEALTHQA_SYSTEM_PROMPT}

Patient's question: {question}

Retrieved context from medical knowledge base:
{evidence}

Answer the patient's question now. Every claim must come from the retrieved context above.
"""


def healthqa_fallback(question: str, retrieved: Dict[str, List[Dict]]) -> str:
    """Template fallback for Health Q&A when Ollama is unavailable."""
    PATIENT_SOURCES = {"medlineplus", "openfda"}

    def _get_tips(n: int = 4) -> List[str]:
        out = []
        for section, items in retrieved.items():
            for item in items:
                chunk = item.get("chunk", item)
                if chunk.get("source") not in PATIENT_SOURCES:
                    continue
                text = _strip_html(chunk.get("text", "").replace("\n", " "))
                if text.startswith("QUESTION:") or text.startswith("SOURCE:"):
                    continue
                text = _sentence_clip(text, 400)
                if text:
                    out.append(f"  • {text}")
                if len(out) >= n:
                    return out
        return out

    tips = _get_tips()
    tips_text = "\n".join(tips) if tips else (
        "  • Rest and stay hydrated.\n"
        "  • Avoid strenuous activities until you feel better.\n"
        "  • Use over-the-counter remedies as directed on the package."
    )
    q_short = question[:100]

    return f"""## 🤔 What This Could Be
Based on your question about "{q_short}", here is some general health information from trusted medical sources.
Common causes vary widely, so only a healthcare provider can give you a personal diagnosis — but this guidance can help you understand your situation and decide what to do next.

## 🏠 Home Care Tips
Many everyday symptoms can be managed at home with these evidence-based steps:
{tips_text}
Remember: these are general suggestions — if your symptoms are severe or unusual, seek medical care.

## 🩺 When to See a Doctor
Schedule an appointment with your doctor if:
  • Your symptoms last more than 3–5 days without improvement
  • Your symptoms are getting worse, not better
  • You have a fever above 101°F (38.3°C) lasting more than 2 days
  • You have an underlying health condition that may be related
  • You feel worried or uncertain — your doctor is always the right call
Your healthcare provider can give you advice tailored specifically to you.

## 🚨 Go to the ER If
Seek emergency care immediately if you experience any of these:
  • Chest pain, pressure, or tightness
  • Sudden difficulty breathing or shortness of breath
  • Sudden severe headache, vision changes, or confusion
  • Signs of severe allergic reaction (face/throat swelling, difficulty swallowing)
  • Loss of consciousness or inability to stay awake
  • Any symptom that feels life-threatening
Trust your instincts — when in doubt, always seek help right away.
"""
