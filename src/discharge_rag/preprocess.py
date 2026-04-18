from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

COMMON_ABBREVIATIONS = {
    # Heart / Cardiovascular
    "hfref": "heart failure with reduced ejection fraction",
    "hfpef": "heart failure with preserved ejection fraction",
    "hf": "heart failure",
    "chf": "congestive heart failure",
    "cad": "coronary artery disease",
    "mi": "myocardial infarction",
    "stemi": "ST-elevation myocardial infarction",
    "nstemi": "non-ST-elevation myocardial infarction",
    "afib": "atrial fibrillation",
    "af": "atrial fibrillation",
    "avr": "aortic valve replacement",
    "cabg": "coronary artery bypass graft surgery",
    "ef": "ejection fraction",
    "lvef": "left ventricular ejection fraction",
    "dvt": "deep vein thrombosis",
    "pe": "pulmonary embolism",
    "svt": "supraventricular tachycardia",
    "vt": "ventricular tachycardia",
    "vfib": "ventricular fibrillation",
    # Blood pressure / Metabolic
    "htn": "hypertension",
    "dm": "diabetes mellitus",
    "dm2": "type 2 diabetes",
    "t2dm": "type 2 diabetes",
    "t1dm": "type 1 diabetes",
    "iddm": "insulin-dependent diabetes mellitus",
    "niddm": "non-insulin-dependent diabetes mellitus",
    "hba1c": "hemoglobin A1c (a measure of average blood sugar)",
    "bmi": "body mass index",
    "hyperlipidemia": "high cholesterol",
    "dyslipidemia": "abnormal cholesterol levels",
    "ldl": "low-density lipoprotein (bad cholesterol)",
    "hdl": "high-density lipoprotein (good cholesterol)",
    # Kidney
    "aki": "acute kidney injury",
    "ckd": "chronic kidney disease",
    "esrd": "end-stage renal disease",
    "egfr": "estimated glomerular filtration rate (a measure of kidney function)",
    "cr": "creatinine (a kidney function marker)",
    # Lungs / Breathing
    "copd": "chronic obstructive pulmonary disease",
    "sob": "shortness of breath",
    "doe": "shortness of breath with exertion",
    "pna": "pneumonia",
    "uri": "upper respiratory infection",
    "osa": "obstructive sleep apnea",
    "cpap": "continuous positive airway pressure (a breathing machine used during sleep)",
    "bipap": "bilevel positive airway pressure (a breathing support machine)",
    # Neurology
    "tia": "transient ischemic attack (mini-stroke)",
    "cva": "stroke",
    "ms": "multiple sclerosis",
    "sz": "seizure",
    # GI
    "gerd": "gastroesophageal reflux disease (acid reflux)",
    "ibs": "irritable bowel syndrome",
    "ibd": "inflammatory bowel disease",
    "uc": "ulcerative colitis",
    "gi": "gastrointestinal",
    # Infection / Immune
    "uti": "urinary tract infection",
    "bac": "bacteremia (bacteria in the blood)",
    "sepsis": "severe infection spreading through the blood",
    "hiv": "human immunodeficiency virus",
    "tb": "tuberculosis",
    # General / Vitals
    "hr": "heart rate",
    "bp": "blood pressure",
    "rr": "respiratory rate",
    "temp": "temperature",
    "o2sat": "oxygen saturation",
    "spo2": "blood oxygen level",
    "wbc": "white blood cell count",
    "hgb": "hemoglobin",
    "plt": "platelets",
    "bun": "blood urea nitrogen (kidney marker)",
    "na": "sodium",
    "k": "potassium",
    "hpi": "history of present illness",
    "pmh": "past medical history",
    "prn": "as needed",
    "po": "by mouth (oral)",
    "iv": "intravenous",
    "bid": "twice daily",
    "tid": "three times daily",
    "qid": "four times daily",
    "qd": "once daily",
    "qhs": "at bedtime",
    "npo": "nothing by mouth",
    "dc": "discharge",
    "f/u": "follow-up",
    "w/u": "workup",
    "r/o": "rule out",
    "s/p": "status post (after a procedure or event)",
    "h/o": "history of",
    "c/o": "complaining of",
    "er": "emergency room",
    "ed": "emergency department",
    "icu": "intensive care unit",
    "ccu": "cardiac care unit",
    "loa": "level of alertness",
    "aox3": "alert and oriented to person, place, and time",
    "wdwn": "well-developed, well-nourished",
    "nak": "no abnormality known",
}

SECTION_PATTERNS = {
    "history": [
        r"history of present illness[:\s]",
        r"\bhpi[:\s]",
        r"hospital course[:\s]",
    ],
    "diagnosis": [
        r"discharge diagnosis(?:es)?[:\s]",
        r"diagnosis(?:es)?[:\s]",
        r"assessment(?: and plan)?[:\s]",
    ],
    "medications": [
        r"discharge medications?[:\s]",
        r"medications? on discharge[:\s]",
        r"medications?[:\s]",
    ],
    "follow_up": [
        r"follow[- ]?up(?: instructions)?[:\s]",
        r"follow[- ]?up appointments?[:\s]",
    ],
    "warning_signs": [
        r"return precautions?[:\s]",
        r"warning signs?[:\s]",
        r"when to call(?: your doctor)?[:\s]",
    ],
}

MED_PATTERN = re.compile(
    r"(?P<drug>[A-Z][a-zA-Z0-9\-]+(?: [A-Z]?[a-zA-Z0-9\-]+)?)"
    r"(?:\s+)(?P<dose>\d+(?:\.\d+)?\s?(?:mg|mcg|g|units|mL))?"
    r"(?:.*?)(?P<freq>daily|twice daily|once daily|every \d+ hours|as needed|bid|tid|qid)?",
    re.IGNORECASE,
)

@dataclass
class ProcessedNote:
    raw_text: str
    cleaned_text: str
    sections: Dict[str, str]
    medications: List[Dict[str, str]]
    normalized_terms: List[str]

def clean_text(text: str) -> str:
    text = re.sub(r"_{2,}", " ", text)
    text = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", " ", text)
    # Preserve newlines (needed for section parsing) — only collapse horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def normalize_abbreviations(text: str) -> Tuple[str, List[str]]:
    normalized = []
    out = text
    for k, v in COMMON_ABBREVIATIONS.items():
        pattern = re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE)
        if pattern.search(out):
            out = pattern.sub(v, out)
            normalized.append(v)
    return out, sorted(set(normalized))

def segment_sections(text: str) -> Dict[str, str]:
    lower = text.lower()
    matches = []
    for section, patterns in SECTION_PATTERNS.items():
        for p in patterns:
            m = re.search(p, lower, flags=re.IGNORECASE)
            if m:
                matches.append((m.start(), section, m.group(0)))
                break
    if not matches:
        return {"general": text}

    matches.sort(key=lambda x: x[0])
    sections: Dict[str, str] = {}
    for i, (start, section, header_text) in enumerate(matches):
        # Skip past the matched header so section content is clean
        content_start = start + len(header_text)
        end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        chunk = text[content_start:end].strip()
        if chunk:
            sections[section] = chunk
    return sections

def extract_medications(text: str) -> List[Dict[str, str]]:
    meds = []
    for match in MED_PATTERN.finditer(text):
        drug = (match.group("drug") or "").strip()
        if not drug or len(drug) < 3:
            continue
        meds.append({
            "drug": drug,
            "dose": (match.group("dose") or "").strip(),
            "frequency": (match.group("freq") or "").strip(),
        })
    dedup = []
    seen = set()
    for m in meds:
        key = tuple(m.items())
        if key not in seen:
            dedup.append(m)
            seen.add(key)
    return dedup[:25]

def normalize_entities_simple(text: str) -> List[str]:
    # Lightweight hook. Replace with UMLS/SNOMED linker (scispaCy) for production.
    known_conditions = [
        "heart failure", "heart failure with reduced ejection fraction",
        "heart failure with preserved ejection fraction", "congestive heart failure",
        "hypertension", "high blood pressure",
        "type 2 diabetes", "type 1 diabetes", "diabetes mellitus",
        "atrial fibrillation", "arrhythmia",
        "acute kidney injury", "chronic kidney disease", "end-stage renal disease",
        "pneumonia", "upper respiratory infection",
        "chronic obstructive pulmonary disease", "asthma",
        "coronary artery disease", "myocardial infarction", "heart attack",
        "stroke", "transient ischemic attack",
        "deep vein thrombosis", "pulmonary embolism",
        "obstructive sleep apnea",
        "gastroesophageal reflux disease", "acid reflux",
        "urinary tract infection",
        "sepsis", "bacteremia",
        "high cholesterol", "high triglycerides",
        "anemia", "hypothyroidism", "hyperthyroidism",
        "osteoporosis", "arthritis", "gout",
        "depression", "anxiety", "bipolar disorder",
        "seizure", "epilepsy",
        "multiple sclerosis", "parkinson disease",
        "obesity",
    ]
    entities = set()
    for term in known_conditions:
        if re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE):
            entities.add(term)
    return sorted(entities)

def preprocess_note(text: str) -> ProcessedNote:
    cleaned = clean_text(text)
    expanded, normalized_abbrevs = normalize_abbreviations(cleaned)
    sections = segment_sections(expanded)
    meds = extract_medications(sections.get("medications", expanded))
    entities = sorted(set(normalized_abbrevs + normalize_entities_simple(expanded)))
    return ProcessedNote(
        raw_text=text,
        cleaned_text=expanded,
        sections=sections,
        medications=meds,
        normalized_terms=entities,
    )
