from __future__ import annotations

from pathlib import Path
import json
import time
import zipfile
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MED_DIR = RAW / "medlineplus"
FDA_DIR = RAW / "openfda"
PLABA_DIR = RAW / "plaba"
PUBMED_DIR = RAW / "pubmed"
MED_DIR.mkdir(parents=True, exist_ok=True)
FDA_DIR.mkdir(parents=True, exist_ok=True)
PLABA_DIR.mkdir(parents=True, exist_ok=True)
PUBMED_DIR.mkdir(parents=True, exist_ok=True)

MEDLINEPLUS_XML_PAGE = "https://medlineplus.gov/xml.html"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def download(url: str, dest: Path, headers: dict | None = None):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"Exists: {dest}")
        return dest
    h = headers or {}
    with requests.get(url, stream=True, timeout=180, headers=h) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=dest.name) as pbar:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    return dest


def _resolve_href(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"https://medlineplus.gov{href}"
    return f"https://medlineplus.gov/xml/{href}"


# ---------------------------------------------------------------------------
# MedlinePlus  (~1,100 topics)
# ---------------------------------------------------------------------------

def discover_medlineplus_urls() -> tuple[str | None, str | None]:
    headers = {"User-Agent": "DischargeRAG-research/1.0 (academic NLP project)"}
    resp = requests.get(MEDLINEPLUS_XML_PAGE, timeout=60, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    xml_url = zip_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "mplus_topics_" in href and href.endswith(".xml") and "group" not in href:
            xml_url = _resolve_href(href)
            break
        if "medlineplus health topic xml" in a.get_text(" ", strip=True).lower() and href.endswith(".xml"):
            xml_url = _resolve_href(href)
            break
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "mplus_topics_compressed_" in href and href.endswith(".zip"):
            zip_url = _resolve_href(href)
            break
    return xml_url, zip_url


def get_medlineplus():
    xml_path = MED_DIR / "medlineplus_topics.xml"
    zip_path = MED_DIR / "medlineplus_topics.zip"
    headers = {"User-Agent": "DischargeRAG-research/1.0 (academic NLP project)"}

    try:
        xml_url, zip_url = discover_medlineplus_urls()
    except Exception as e:
        print(f"[MedlinePlus] Page scrape failed: {e}. Trying known URL pattern...")
        xml_url, zip_url = None, None

    # Fallback: try known date-stamped URLs
    if not xml_url:
        import datetime
        for months_back in range(0, 6):
            d = datetime.date.today().replace(day=1)
            for _ in range(months_back):
                d = (d - datetime.timedelta(days=1)).replace(day=1)
            candidate = f"https://medlineplus.gov/xml/mplus_topics_{d.strftime('%Y-%m-%d')}.xml"
            r = requests.head(candidate, headers=headers, timeout=10)
            if r.status_code == 200:
                xml_url = candidate
                break

    if xml_url:
        try:
            download(xml_url, xml_path, headers=headers)
            print(f"Wrote {xml_path}")
            return
        except Exception as e:
            print(f"Direct XML download failed: {e}")

    if zip_url:
        download(zip_url, zip_path, headers=headers)
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [m for m in zf.namelist() if m.endswith(".xml") and "group" not in m.lower()]
            if not members:
                raise RuntimeError("ZIP downloaded but no MedlinePlus topic XML found inside")
            with zf.open(members[0]) as src, open(xml_path, "wb") as dst:
                dst.write(src.read())
        print(f"Extracted {xml_path} from {zip_path}")
        return

    print(
        "\n[MedlinePlus] Automatic download blocked.\n"
        "  1. Go to: https://medlineplus.gov/xml.html\n"
        "  2. Download the 'MedlinePlus Health Topic XML' file.\n"
        f"  3. Save it to: {xml_path}\n"
    )


# ---------------------------------------------------------------------------
# openFDA Drug Labels  (~16,000 records)
# ---------------------------------------------------------------------------

def get_openfda(limit: int = 16000):
    out = FDA_DIR / "drug_labels.jsonl"
    if out.exists() and out.stat().st_size > 0:
        existing = sum(1 for _ in open(out))
        if existing >= limit:
            print(f"Exists: {out} ({existing} records)")
            return
        print(f"Resuming openFDA download from {existing} records...")
        skip_start = existing
    else:
        skip_start = 0

    batch = 100
    written = skip_start
    mode = "a" if skip_start else "w"
    with open(out, mode, encoding="utf-8") as f:
        with tqdm(total=limit, initial=written, desc="openFDA drug labels") as pbar:
            while written < limit:
                url = f"https://api.fda.gov/drug/label.json?limit={batch}&skip={written}"
                try:
                    resp = requests.get(url, timeout=120)
                    resp.raise_for_status()
                    results = resp.json().get("results", [])
                    if not results:
                        break
                    for row in results:
                        f.write(json.dumps(row) + "\n")
                        written += 1
                        pbar.update(1)
                        if written >= limit:
                            break
                    time.sleep(0.25)  # be polite to FDA API
                except Exception as e:
                    print(f"\n[openFDA] Error at skip={written}: {e}. Retrying in 5s...")
                    time.sleep(5)
    print(f"Wrote {out} with {written} records")


# ---------------------------------------------------------------------------
# PubMed Abstracts via NCBI Entrez  (~3,000 abstracts)
# Covers discharge-relevant clinical topics — free, no API key needed.
# ---------------------------------------------------------------------------

PUBMED_QUERIES = [
    "heart failure patient discharge instructions",
    "hypertension medication adherence",
    "type 2 diabetes self management",
    "atrial fibrillation anticoagulation patient education",
    "chronic kidney disease diet management",
    "COPD exacerbation discharge planning",
    "pneumonia treatment outpatient followup",
    "deep vein thrombosis treatment home care",
    "stroke rehabilitation discharge",
    "myocardial infarction secondary prevention",
    "sepsis discharge care instructions",
    "urinary tract infection antibiotic treatment",
    "asthma inhaler patient education",
    "hospital readmission prevention",
    "medication reconciliation discharge",
    "warfarin patient education INR monitoring",
    "insulin therapy type 1 diabetes",
    "blood pressure monitoring home",
    "wound care post surgical discharge",
    "pain management after surgery discharge",
    "heart failure readmission risk factors",
    "polypharmacy elderly discharge medication safety",
    "antibiotic resistance patient education",
    "chronic obstructive pulmonary disease self management",
    "post myocardial infarction cardiac rehabilitation",
    "hypertensive crisis emergency department discharge",
    "diabetic foot care patient education",
    "renal failure diet restrictions patient",
    "anticoagulation therapy management atrial fibrillation",
    "fall prevention elderly discharge instructions",
    "depression anxiety hospital discharge mental health",
    "opioid medication discharge instructions pain",
    "nutrition support post surgery discharge",
    "sleep apnea CPAP adherence patient",
    "osteoporosis bisphosphonate therapy discharge",
    "thyroid disorder medication compliance",
    "heart valve surgery discharge care",
    "chemotherapy side effects patient education",
    "palliative care discharge home hospice",
    "pediatric discharge instructions parents education",
]

ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _fetch_pubmed_ids(query: str, retmax: int = 50) -> list[str]:
    url = f"{ENTREZ_BASE}/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmax": retmax, "retmode": "json", "usehistory": "n"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def _fetch_pubmed_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    url = f"{ENTREZ_BASE}/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    docs = []
    try:
        root = ET.fromstring(r.content)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else "unknown"
            title_el = article.find(".//ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else ""
            abstract_el = article.find(".//AbstractText")
            abstract = "".join(abstract_el.itertext()) if abstract_el is not None else ""
            if abstract and len(abstract) > 80:
                docs.append({"pmid": pmid, "title": title, "abstract": abstract})
    except ET.ParseError:
        pass
    return docs


def get_pubmed(target: int = 3000):
    out = PUBMED_DIR / "pubmed_abstracts.jsonl"
    if out.exists() and out.stat().st_size > 0:
        existing = sum(1 for _ in open(out))
        if existing >= target:
            print(f"Exists: {out} ({existing} records)")
            return
        print(f"Resuming PubMed download from {existing} records...")
    else:
        existing = 0

    seen_pmids: set[str] = set()
    if existing:
        with open(out, "r") as f:
            for line in f:
                row = json.loads(line)
                seen_pmids.add(row.get("pmid", ""))

    written = existing
    per_query = max(50, (target // len(PUBMED_QUERIES)) + 10)

    with open(out, "a" if existing else "w", encoding="utf-8") as f:
        with tqdm(total=target, initial=written, desc="PubMed abstracts") as pbar:
            for query in PUBMED_QUERIES:
                if written >= target:
                    break
                try:
                    pmids = _fetch_pubmed_ids(query, retmax=per_query)
                    new_pmids = [p for p in pmids if p not in seen_pmids]
                    if not new_pmids:
                        continue
                    abstracts = _fetch_pubmed_abstracts(new_pmids)
                    for doc in abstracts:
                        if written >= target:
                            break
                        if doc["pmid"] in seen_pmids:
                            continue
                        seen_pmids.add(doc["pmid"])
                        f.write(json.dumps(doc) + "\n")
                        written += 1
                        pbar.update(1)
                    time.sleep(0.4)  # NCBI rate limit: max 3 req/sec without API key
                except Exception as e:
                    print(f"\n[PubMed] Error for query '{query}': {e}")
                    time.sleep(3)

    print(f"Wrote {out} with {written} PubMed abstracts")


# ---------------------------------------------------------------------------
# PLABA  (~750 plain-language abstract pairs)
# ---------------------------------------------------------------------------

def get_plaba():
    out = PLABA_DIR / "plaba.jsonl"
    if out.exists() and out.stat().st_size > 0:
        print(f"Exists: {out}")
        return

    BASE = "https://physionet.org/files/plaba-bionlp/1.0.0"
    index_url = f"{BASE}/RECORDS"
    print("Fetching PLABA record index...")
    try:
        resp = requests.get(index_url, timeout=60)
        resp.raise_for_status()
        record_names = [r.strip() for r in resp.text.strip().splitlines() if r.strip()]
    except Exception as e:
        print(f"Could not fetch PLABA record index: {e}")
        record_names = []

    written = 0
    with open(out, "w", encoding="utf-8") as f:
        if record_names:
            for name in tqdm(record_names, desc="PLABA records"):
                try:
                    r = requests.get(f"{BASE}/{name}", timeout=60)
                    r.raise_for_status()
                    data = r.json()
                    row = {
                        "source_text": data.get("source_abstract", data.get("abstract", data.get("source_text", ""))),
                        "plain_language_text": data.get("plain_language_abstract", data.get("plain_language", data.get("plain_language_text", ""))),
                        "question": data.get("question", ""),
                    }
                    if row["source_text"] and row["plain_language_text"]:
                        f.write(json.dumps(row) + "\n")
                        written += 1
                except Exception:
                    continue
        else:
            for fname in ["plaba.jsonl", "plaba_train.jsonl", "data.jsonl"]:
                try:
                    r = requests.get(f"{BASE}/{fname}", timeout=120, stream=True)
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            f.write(json.dumps(json.loads(line)) + "\n")
                            written += 1
                    if written:
                        break
                except Exception:
                    continue

    if written == 0:
        out.unlink(missing_ok=True)
        print(
            "\n[PLABA] Automatic download failed.\n"
            "  1. Go to: https://physionet.org/content/plaba-bionlp/\n"
            "  2. Create a free PhysioNet account (no credentialing required).\n"
            "  3. Accept the data use agreement and download.\n"
            f"  4. Place the .jsonl file at: {out}\n"
        )
    else:
        print(f"Wrote {out} with {written} PLABA records")


# ---------------------------------------------------------------------------
# Corpus summary
# ---------------------------------------------------------------------------

def print_corpus_summary():
    sources = {
        "MedlinePlus": MED_DIR / "medlineplus_topics.xml",
        "openFDA":     FDA_DIR / "drug_labels.jsonl",
        "PLABA":       PLABA_DIR / "plaba.jsonl",
        "PubMed":      PUBMED_DIR / "pubmed_abstracts.jsonl",
    }
    total = 0
    print("\n=== Corpus Summary ===")
    for name, path in sources.items():
        if not path.exists():
            print(f"  {name}: MISSING")
            continue
        if path.suffix == ".xml":
            # count health-topic elements
            try:
                tree = ET.parse(str(path))
                count = sum(1 for _ in tree.getroot().iter("health-topic"))
            except Exception:
                count = "?"
        else:
            count = sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
        total += count if isinstance(count, int) else 0
        print(f"  {name}: {count:,} documents")
    print(f"  ─────────────────────")
    print(f"  TOTAL: {total:,} documents")
    if total >= 20000:
        print("  ✓ Corpus target of 20,000 reached.")
    else:
        print(f"  ✗ Still need {20000 - total:,} more documents to reach 20,000.")
    print()


if __name__ == "__main__":
    print("Downloading open corpora for DischargeRAG...")
    print("Target: 20,000 total documents\n")
    get_medlineplus()
    get_openfda()
    get_pubmed()
    get_plaba()
    print_corpus_summary()
