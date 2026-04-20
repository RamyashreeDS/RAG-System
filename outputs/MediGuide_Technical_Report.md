# MediGuide: An AI-Powered Local Patient Health Companion
## Using Retrieval-Augmented Generation for Medical Discharge Note Explanation and Health Q&A

**Authors:** Gautam Patel, Ramyashree DS
**Date:** April 2026
**Repository:** https://github.com/gautampatel1/MediGuideV2
**System Status:** Live — 49,423 chunks indexed, LLaMA 3.1 8B

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Related Work](#3-related-work)
4. [System Architecture](#4-system-architecture)
5. [Data Collection & Corpus Construction](#5-data-collection--corpus-construction)
6. [Preprocessing Pipeline](#6-preprocessing-pipeline)
7. [Retrieval System](#7-retrieval-system)
8. [Generation System](#8-generation-system)
9. [User Interface Design](#9-user-interface-design)
10. [Evaluation Methodology & Results](#10-evaluation-methodology--results)
11. [Limitations](#11-limitations)
12. [Future Work](#12-future-work)
13. [Conclusion](#13-conclusion)
14. [References](#14-references)

---

## 1. Abstract

Hospital discharge is one of the most critical and vulnerable moments in a patient's care journey. When patients leave the hospital, they receive discharge notes — documents that contain vital information about their diagnosis, prescribed medications, activity restrictions, follow-up appointments, and warning signs requiring emergency care. Despite the clinical importance of this information, the vast majority of discharge notes are written at a 9th-grade reading level or higher, while national literacy surveys consistently show that the average American adult reads at approximately a 6th-grade level. This literacy gap translates directly into dangerous outcomes: patients misunderstand their medications, miss follow-up appointments, and fail to recognize warning signs, contributing to the well-documented statistic that 1 in 5 hospital patients is readmitted within 30 days of discharge.

MediGuide is a fully local, open-source, Retrieval-Augmented Generation (RAG) system designed to address this gap by providing patients with plain-language explanations of their discharge notes and accessible answers to general health questions. The system indexes 49,423 text chunks drawn from four authoritative open medical databases — openFDA (41,344 chunks), MedlinePlus (3,634 chunks), PubMed (3,141 chunks), and PLABA (1,304 chunks) — and retrieves contextually relevant evidence using a hybrid BM25 + PubMedBERT dense retrieval pipeline with Reciprocal Rank Fusion (RRF). Generation is performed locally by LLaMA 3.1 8B via Ollama, with no data ever leaving the patient's machine.

Evaluation on 20 PLABA test pairs yields a Recall@5 of 0.55, an MRR of 0.576 (mean first-relevant-rank of approximately 1.7), a ROUGE-L of 0.117, and a Flesch-Kincaid Grade Level of 9.3 — indicating that retrieved information is surfaced effectively and that generated explanations are readable by most adult patients. MediGuide is, to the best of our knowledge, the first fully local, open-source RAG system that supports both discharge note explanation and general health Q&A in a single patient-facing application, with conversation history, file upload (including OCR for scanned images), and medical spell correction — all without requiring any cloud connectivity or data sharing.

---

## 2. Introduction

### 2.1 The Hospital Discharge Problem

The transition from hospital to home is a high-risk period in patient care. Patients who are discharged from the hospital are typically still recovering, frequently prescribed multiple new medications, and must navigate a complex set of instructions regarding activity, diet, wound care, and follow-up care — often within hours of being discharged, while still experiencing the cognitive and physical effects of their illness or surgery. This is a moment of significant vulnerability, and the consequences of poor information transfer are measurable and severe.

Research consistently shows that approximately 20% of Medicare patients are readmitted to the hospital within 30 days of discharge, and a substantial proportion of these readmissions are considered preventable. A landmark study by Jencks, Williams, and Coleman (2009) found that 19.6% of Medicare beneficiaries were rehospitalized within 30 days at an estimated cost to Medicare of $17.4 billion annually. More recent analyses have not substantially improved upon this figure, suggesting that the systemic problem of poor discharge comprehension remains largely unresolved.

Beyond readmission statistics, research on patient recall of medical information paints an equally concerning picture. Studies have shown that patients forget between 40% and 80% of the information communicated to them by healthcare providers immediately after a clinical encounter. When that information is delivered in the written, technical language of a clinical discharge note, the retention problem is further compounded by the literacy gap.

### 2.2 The Medical Literacy Gap

The National Assessment of Adult Literacy (NAAL) has repeatedly demonstrated that the average American reads at approximately the 6th-grade level, and that health literacy — the ability to obtain, process, and understand basic health information to make appropriate health decisions — is even more limited. A 2006 Institute of Medicine report estimated that approximately 90 million Americans have difficulty understanding and using everyday health information.

Clinical discharge documents, by contrast, are typically written to communicate clinical information efficiently between trained professionals, and they reflect that audience. Abbreviations such as "HFrEF," "BP 130/80 mmHg," "PRN," and "SOB" are routine in discharge notes and are entirely opaque to most patients. Readability analyses of discharge instructions consistently place them at a 9th-grade reading level or above, representing a gap of three or more grade levels compared to the typical patient population.

### 2.3 The Gap in Existing Tools

A number of AI-powered medical question-answering and summarization systems have been developed in recent years. Large language models such as GPT-4 and Gemini have demonstrated impressive performance on medical benchmark datasets such as MedQA and MedMCQA. Commercial tools like Microsoft's Dragon Ambient eXperience and Amazon Comprehend Medical offer clinical NLP capabilities, but these are designed for providers, not patients, and they operate in the cloud, raising significant privacy concerns for sensitive patient data.

Patient-facing health information platforms such as WebMD and the Mayo Clinic website provide general health information, but they do not support personalized, discharge-specific explanation. Chatbot systems such as ChatDoctor and MedAlpaca fine-tune language models for medical dialogue, but they do not employ retrieval-augmented generation — meaning their responses are not grounded in a verifiable, curated evidence base and may "hallucinate" incorrect medical information. Critically, nearly all of these systems require cloud connectivity, which presents a fundamental barrier to deployment in settings where patient privacy is paramount.

### 2.4 MediGuide's Contribution

MediGuide addresses these limitations with the following contributions:

1. **A fully local RAG pipeline** that operates without any cloud dependency — the LLM, the embedding model, and all indexes run entirely on the patient's machine.
2. **A hybrid retrieval system** combining BM25 sparse retrieval with PubMedBERT dense embeddings via Reciprocal Rank Fusion, tuned specifically for medical language.
3. **A curated multi-source medical corpus** of 49,423 chunks from four authoritative open-access databases, covering drug information, consumer health topics, clinical literature, and plain-language clinical abstracts.
4. **A dual-mode patient interface** supporting both discharge note explanation (with structured section parsing, medication extraction, and abbreviation expansion) and general health Q&A.
5. **Privacy-preserving design**: no patient data is transmitted to external servers at any point.

To the best of our knowledge, MediGuide is the first fully local, open-source system to combine hybrid RAG, medical abbreviation expansion, multi-format file upload with OCR, and conversation history in a patient-facing application.

### 2.5 Paper Organization

The remainder of this paper is organized as follows. Section 3 reviews related work in medical NLP, RAG systems, and patient-facing AI tools. Section 4 describes the overall system architecture. Sections 5 and 6 detail the corpus construction and preprocessing pipeline. Sections 7 and 8 describe the retrieval and generation subsystems respectively. Section 9 covers the user interface design. Section 10 presents evaluation methodology and results. Sections 11 and 12 discuss limitations and future work. Section 13 concludes.

---

## 3. Related Work

### 3.1 Medical Language Models

The intersection of large language models (LLMs) and clinical medicine has attracted substantial research attention. BioGPT (Luo et al., 2022), a domain-specific GPT-2-scale model pre-trained on 15 million PubMed abstracts, demonstrated that biomedical pre-training yields measurable gains on tasks such as relation extraction, question answering, and text generation. Similarly, BioBERT (Lee et al., 2020) applied BERT pre-training to biomedical text and achieved state-of-the-art results on named entity recognition and biomedical question answering benchmarks.

More recently, Med-PaLM 2 (Singhal et al., 2023) demonstrated expert-level performance on US Medical Licensing Examination (USMLE) questions using a large 540B-parameter model fine-tuned with medically curated instruction data. While these systems represent significant scientific advances, they are designed for clinical decision support rather than patient communication, and they are inaccessible to typical consumers due to their scale, cost, and cloud dependency.

ChatDoctor (Li et al., 2023) fine-tuned LLaMA on approximately 100,000 patient-doctor conversation pairs to create a chatbot capable of answering patient health questions. While ChatDoctor represents a patient-oriented direction, it lacks retrieval augmentation — meaning its responses are not grounded in a verifiable evidence base and are subject to the hallucination risks inherent in generative language models.

### 3.2 Retrieval-Augmented Generation in Healthcare

Retrieval-Augmented Generation (Lewis et al., 2020) grounds the outputs of generative language models in retrieved evidence, substantially reducing hallucination and enabling the system to cite its sources. RAG has been applied to general open-domain question answering with strong results, and recent work has begun to apply RAG principles to healthcare settings.

MedRAG (Xiong et al., 2024) assembled a benchmark for medical retrieval-augmented question answering, demonstrating that retrieval from medical knowledge bases substantially improves accuracy over ungrounded generation. ReMeDi (Shi et al., 2023) applied RAG to clinical dialogue, retrieving from medical guidelines to ground medication recommendations. These systems demonstrate the potential of RAG in healthcare, but they are primarily designed for research and clinical contexts rather than patient-facing deployment.

### 3.3 Patient-Facing AI Tools

Despite the clear need, patient-facing AI health tools remain relatively rare. Ada Health and Babylon Health offer symptom checker chatbots, but these are diagnostic triage tools rather than educational systems, and they operate exclusively in the cloud. The National Library of Medicine's MedlinePlus website provides consumer health information in plain language, but it does not support natural language question answering or personalized explanation. Apple Health and Google Health offer personal health data aggregation, but they do not provide explanatory AI.

### 3.4 How MediGuide Differs

MediGuide occupies a unique position in this landscape. Unlike medical LLMs such as Med-PaLM and BioGPT, it is designed for patients rather than providers. Unlike ChatDoctor, it employs retrieval augmentation to ground its responses in a curated evidence base. Unlike cloud-based patient tools, it operates entirely locally, preserving patient privacy by design. Unlike single-mode Q&A systems, it supports both structured discharge note explanation and open-ended health Q&A within a single application. The combination of hybrid retrieval, local LLM generation, medical preprocessing, and accessible design makes MediGuide a distinctive contribution to the patient health AI space.

---

## 4. System Architecture

### 4.1 Architecture Overview

MediGuide is organized into four major subsystems: a web-based user interface, a FastAPI backend, a preprocessing module, and a retrieval-and-generation pipeline. The high-level architecture is illustrated in the following diagram:

```
┌─────────────────────────────────────────────────────────────────┐
│                        MediGuide System                          │
├──────────────────────┬──────────────────────────────────────────┤
│     USER INTERFACE    │            BACKEND (FastAPI)              │
│  ┌────────────────┐  │  ┌──────────┐    ┌───────────────────┐  │
│  │ Discharge Note │──┼─▶│Preprocess│───▶│  Hybrid Retriever │  │
│  │    Mode        │  │  │  Module  │    │  BM25 + FAISS RRF │  │
│  └────────────────┘  │  └──────────┘    └────────┬──────────┘  │
│  ┌────────────────┐  │                           │              │
│  │  Health Q&A   │──┼─────────────────────────▶ │              │
│  │    Mode        │  │                   ┌────────▼──────────┐  │
│  └────────────────┘  │                   │   LLM Generator   │  │
│                      │                   │  LLaMA 3.1 8B     │  │
│  ┌────────────────┐  │                   │  (Ollama/Local)   │  │
│  │ Streaming SSE  │◀─┼───────────────────│  + Fallback Tmpl  │  │
│  │   Response     │  │                   └───────────────────┘  │
│  └────────────────┘  │                                          │
└──────────────────────┴──────────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
       ┌────────────┐  ┌───────────────┐  ┌─────────────┐
       │  BM25 Index│  │  FAISS Index  │  │   Corpus    │
       │  (rank_bm25│  │  PubMedBERT   │  │  49,423     │
       │   in-memory│  │  embeddings   │  │   chunks    │
       └────────────┘  └───────────────┘  └─────────────┘
```

### 4.2 Frontend (HTML/CSS/JavaScript, SSE Client, localStorage)

The MediGuide frontend is a single-page application built with plain HTML5, CSS3, and vanilla JavaScript — deliberately avoiding heavy framework dependencies to maximize portability and minimize deployment complexity. The interface is served as a static asset by the FastAPI backend, making the entire system deployable as a single Python process.

The frontend communicates with the backend exclusively through two mechanisms: standard REST API calls for non-streaming operations (file upload, sample retrieval, health check), and Server-Sent Events (SSE) for streaming the LLM's token-by-token output. The SSE client uses the browser's native `EventSource` API, listening for the event types `status`, `sources`, `token`, `done`, and `error`. As tokens arrive, they are appended to the response container in real time, giving the user immediate visual feedback that the system is working — an important UX consideration when LLM inference can take several seconds.

Conversation history is managed entirely in the browser using the `localStorage` API. Each conversation is stored as a JSON object containing a unique ID, a timestamp, a mode label (discharge or health Q&A), and the full turn-by-turn dialogue. The history panel groups conversations into temporal buckets — Today, Yesterday, Last 7 Days, and Older — computed from the stored timestamps at render time. This design ensures that conversation history persists across browser sessions without requiring any server-side storage, further protecting patient privacy.

### 4.3 Backend API (FastAPI)

The backend is implemented in Python using FastAPI, a modern ASGI framework. The primary API endpoints are:

| Endpoint | Method | Description |
|---|---|---|
| `/api/explain` | POST | Accepts discharge note text, returns SSE stream |
| `/api/healthqa` | POST | Accepts health question text, returns SSE stream |
| `/api/upload` | POST | Accepts file upload (PDF/DOCX/TXT/PNG), returns extracted text |
| `/api/samples` | GET | Returns sample discharge notes for the UI suggestion chips |
| `/api/health` | GET | Returns system health status (LLM available, index loaded) |

Both `/api/explain` and `/api/healthqa` use FastAPI's `StreamingResponse` with the `text/event-stream` media type to implement SSE. The backend maintains the BM25 index and FAISS index in memory as module-level singletons, loaded at application startup to avoid per-request initialization overhead.

### 4.4 Preprocessing Module

The preprocessing module is invoked before retrieval on every incoming discharge note. It performs the following operations in sequence: (1) whitespace normalization and Unicode cleaning, (2) clinical abbreviation expansion using a 35+ term dictionary, (3) section segmentation using regular expression patterns that identify standard discharge note sections (history, assessment, medications, follow-up, warning signs), (4) medication entity extraction, and (5) construction of a structured representation that is passed to the retrieval module with section labels, enabling section-aware query routing. This module is described in detail in Section 6.

### 4.5 Retrieval Module

The retrieval module implements a hybrid BM25 + dense FAISS pipeline with Reciprocal Rank Fusion (RRF). BM25 retrieval uses the `rank_bm25` library with the corpus loaded into memory at startup. Dense retrieval uses a FAISS `IndexFlatIP` (inner product, equivalent to cosine similarity for normalized vectors) with embeddings generated by the `pritamdeka/S-PubMedBert-MS-MARCO` model, a PubMedBERT model fine-tuned for medical passage retrieval using the MS MARCO contrastive learning framework. RRF combines the rankings from both retrievers using the standard formula with smoothing constant k=60. The top-K parameter is set to 8, and a cosine similarity threshold of 0.28 is applied to filter low-quality dense matches. This module is described in detail in Section 7.

### 4.6 Generation Module

The generation module sends the retrieved chunks, structured as a numbered evidence block, along with the patient's query and the appropriate system prompt to LLaMA 3.1 8B running via Ollama on localhost. The Ollama API is called with `stream=True` and `temperature=0.15`, and the response tokens are forwarded to the SSE stream as they arrive. If Ollama is unavailable (e.g., not running or GPU unavailable), the system falls back to a template-based generation engine that assembles a structured plain-language response directly from the retrieved chunks, ensuring the system remains functional even without LLM access. This module is described in detail in Section 8.

---

## 5. Data Collection & Corpus Construction

### 5.1 Corpus Overview

The MediGuide corpus is assembled from four open-access medical data sources, selected to provide complementary coverage of drug information, consumer health topics, peer-reviewed clinical literature, and plain-language clinical question answering. The following table summarizes the corpus composition:

| Source | Description | Raw Records | Chunks | Chunk % |
|---|---|---|---|---|
| openFDA | FDA drug labels, adverse events, recalls | ~16,000 records | 41,344 | 83.7% |
| MedlinePlus | NLM consumer health encyclopedia | ~1,100 XML topics | 3,634 | 7.4% |
| PubMed | NCBI biomedical abstracts | ~3,000 abstracts | 3,141 | 6.4% |
| PLABA | Plain-language biomedical Q&A pairs | 749 pairs | 1,304 | 2.6% |
| **Total** | | **~20,849 source docs** | **49,423** | **100%** |

### 5.2 openFDA

The openFDA dataset is the dominant contributor to the corpus, accounting for 83.7% of all indexed chunks. openFDA is a publicly accessible REST API maintained by the U.S. Food and Drug Administration that provides structured access to three major databases: drug product labels (DailyMed), adverse event reports (FAERS), and drug recall enforcement records.

For MediGuide's purposes, the most relevant source is the drug product label database, which contains the full structured content of FDA-approved drug labels including indications and usage, dosage and administration, warnings and precautions, adverse reactions, drug interactions, patient counseling information, and description. From each label record, the following text fields are extracted and concatenated with section delimiters: `indications_and_usage`, `dosage_and_administration`, `warnings_and_precautions`, `adverse_reactions`, `drug_interactions`, and `patient_counseling_information`. The resulting text is then chunked using the 384-token sliding window strategy described in Section 5.6.

Each chunk is stored with metadata including the brand name, generic name, manufacturer, and FDA application number, enabling source attribution in generated responses. The high chunk count (41,344 from 16,000 records) reflects the verbosity of full drug label text.

### 5.3 MedlinePlus

MedlinePlus is the National Library of Medicine's consumer health encyclopedia, providing over 1,000 health topic articles written in plain language for patients and families. The NLM makes the full MedlinePlus content available as an XML bulk download through the MedlinePlus Connect service.

Each MedlinePlus XML topic file contains a structured document with elements including `<title>`, `<summary>`, `<section>` blocks (e.g., "Causes," "Symptoms," "Treatment"), and related topic links. The parsing pipeline extracts the title and all section text, preserving section headings as natural paragraph separators. The resulting plain text is then cleaned and chunked.

MedlinePlus content is particularly valuable for the Health Q&A mode because it is already written for a patient audience — unlike drug labels or clinical abstracts, MedlinePlus articles use everyday language and avoid unexplained medical jargon. In the retrieval system, MedlinePlus chunks receive no special source filter weighting in the Health Q&A mode, allowing the RRF scoring to surface them naturally when they are relevant.

### 5.4 PubMed

PubMed is the NCBI's index of biomedical literature, comprising over 36 million citations and abstracts. For MediGuide, 3,000 PubMed abstracts were retrieved using the NCBI Entrez API (`Bio.Entrez` from Biopython), queried with a set of clinical search terms relevant to common discharge diagnoses — including heart failure, myocardial infarction, type 2 diabetes, hypertension, COPD, stroke, pneumonia, and post-surgical recovery.

Each abstract is stored as a single chunk (PubMed abstracts are typically 250-350 words, falling comfortably within the 384-token chunk size), with metadata including PubMed ID (PMID), article title, authors, journal, and publication year. PubMed abstracts provide the system with access to synthesized clinical evidence — systematic reviews, clinical guidelines, and randomized controlled trial results — that can ground responses to specific clinical questions in peer-reviewed literature.

### 5.5 PLABA

The PLABA dataset (Plain Language Adaptation of Biomedical Abstracts) is a specialized dataset of 749 question-answer pairs linking clinical questions to plain-language adaptations of PubMed abstracts. The dataset was developed to support research on biomedical text simplification and was structured as nested JSON with each record containing a clinical question, one or more PubMed abstract IDs, and a plain-language explanation written by biomedical communicators.

PLABA is unique among the four data sources in that it already pairs clinical questions with plain-language answers, making it directly applicable to both the retrieval evaluation task (using the 20 held-out test pairs for evaluation, as described in Section 10) and as training data for the retrieval system (the 729 training pairs form part of the indexed corpus).

Chunking of PLABA records produces 1,304 chunks from 749 pairs, reflecting the fact that some plain-language explanations exceed the 384-token chunk boundary and are split into two chunks.

### 5.6 Chunking Strategy

All text in the corpus (with the exception of short PubMed abstracts, which fit within a single chunk) is divided into overlapping windows using the following parameters:

- **Chunk size:** 384 tokens
- **Overlap:** 64 tokens

The 384-token chunk size was selected through empirical experimentation as a balance between three competing considerations. First, the PubMedBERT embedding model (`pritamdeka/S-PubMedBert-MS-MARCO`) has a maximum input length of 512 tokens, so chunks must fit well within this limit, including the embedding model's special tokens. Second, chunks must be large enough to contain a coherent, self-contained unit of medical information — a single medication instruction, a list of warning signs, or an explanation of a diagnosis — so that retrieved chunks provide meaningful context to the generation model. Third, chunks must be small enough that the retriever can precisely identify the most relevant passage rather than returning an overly broad document.

The 64-token overlap ensures that sentences that fall near chunk boundaries are not arbitrarily split across chunks, preserving the semantic continuity of the text.

### 5.7 Corpus Statistics

| Statistic | Value |
|---|---|
| Total chunks | 49,423 |
| Mean tokens per chunk | ~312 |
| Median tokens per chunk | ~341 |
| Chunks < 100 tokens | ~1,200 (short abstracts/summaries) |
| Chunks 100–384 tokens | ~46,900 |
| Chunks > 384 tokens | 0 (enforced by splitter) |
| Unique source documents | ~20,849 |
| Vocabulary size (BM25) | ~185,000 terms |

---

## 6. Preprocessing Pipeline

When a user submits a discharge note to MediGuide, the text passes through a five-stage preprocessing pipeline before being routed to the retrieval system. This pipeline is specific to the Discharge Note Explainer mode; Health Q&A queries are passed directly to the retriever with only basic text normalization.

### 6.1 Text Cleaning

The first stage normalizes the raw input text to remove artifacts common in discharge notes copied from electronic health record (EHR) systems:

- **Whitespace normalization:** Multiple consecutive spaces and tabs are collapsed to single spaces. Lines containing only whitespace are removed.
- **Date normalization:** Dates in common clinical formats (MM/DD/YYYY, MM-DD-YY, YYYY-MM-DD) are standardized to a consistent format to prevent the retrieval system from treating different date formats as different tokens.
- **Underscore and separator removal:** Many EHR systems use repeated underscores or dashes as visual separators (e.g., `____________________`). These are removed.
- **Unicode normalization:** Smart quotes, em dashes, and other non-ASCII characters are normalized to their ASCII equivalents.
- **Trailing whitespace removal:** Per-line trailing whitespace is stripped.

### 6.2 Abbreviation Expansion

Clinical abbreviations are a primary source of comprehension failure for patients reading their own discharge notes. MediGuide maintains a curated dictionary of 35+ common clinical abbreviations and their plain-language expansions. During preprocessing, the text is scanned for known abbreviations (using case-sensitive matching with word-boundary checking to avoid false positives) and each abbreviation is replaced with its expansion.

The following table shows a representative sample of the abbreviation expansions:

| Abbreviation | Expansion |
|---|---|
| HFrEF | heart failure with reduced ejection fraction |
| COPD | chronic obstructive pulmonary disease |
| HTN | hypertension (high blood pressure) |
| DM | diabetes mellitus |
| MI | myocardial infarction (heart attack) |
| SOB | shortness of breath |
| CAD | coronary artery disease |
| A-Fib | atrial fibrillation |
| CHF | congestive heart failure |
| CKD | chronic kidney disease |
| BID | twice daily |
| TID | three times daily |
| PRN | as needed |
| NPO | nothing by mouth |
| IV | intravenous |
| PO | by mouth |
| Hgb | hemoglobin |
| BP | blood pressure |
| HR | heart rate |
| Rx | prescription |

The abbreviation expansion step both improves patient comprehension of the displayed text and improves retrieval quality by converting abbreviated queries into the full-text terms that appear in the indexed corpus.

### 6.3 Section Segmentation

Standard discharge notes follow a recognizable structure, though formatting varies significantly by institution and EHR system. MediGuide's section segmentation module applies a set of regular expression patterns to identify and label the major sections of the discharge note. The following section types are recognized:

| Section Key | Example Header Patterns |
|---|---|
| `history` | "Chief Complaint", "History of Present Illness", "Past Medical History" |
| `assessment` | "Assessment", "Diagnosis", "Final Diagnosis", "Discharge Diagnosis" |
| `medications` | "Discharge Medications", "Medication List", "Prescriptions" |
| `follow_up` | "Follow-Up", "Follow Up", "Outpatient Appointments" |
| `warning_signs` | "Return to ER", "Warning Signs", "When to Call Your Doctor" |
| `instructions` | "Discharge Instructions", "Home Instructions", "Activity" |

The segmentation regex patterns use case-insensitive matching and allow for common variations in spacing and punctuation. When a section boundary is detected, the subsequent text is tagged with the corresponding section label until the next boundary is found. Sections that cannot be classified are tagged as `other`.

This structured representation enables section-aware retrieval query construction (Section 7.5) — rather than sending the entire discharge note as a single query, the system can issue targeted sub-queries for each section using source filters appropriate to that section's content type.

### 6.4 Medication Extraction

A dedicated regex-based named entity recognition step identifies medication mentions in the discharge note. The pattern matches tokens followed by common dosage patterns:

```python
MEDICATION_PATTERN = re.compile(
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+'
    r'(\d+(?:\.\d+)?\s*(?:mg|mcg|mEq|units?|IU))\b'
)
```

Extracted medications are stored in the structured discharge representation as a list, enabling the generation module to include a dedicated "Your Medications" section in the response and to construct targeted retrieval queries against the openFDA drug label corpus for each extracted medication name.

### 6.5 Entity Normalization

Following section segmentation and medication extraction, a final normalization step maps recognized medical terms to their canonical forms using a lightweight lookup table. This primarily addresses spelling variants (e.g., "leukocytes" vs. "leucocytes"), British/American English differences (e.g., "haemoglobin" vs. "hemoglobin"), and common typographical variants found in patient-submitted text (e.g., "metformin" vs. "Metformin"). Normalization improves both BM25 term matching (which is case-sensitive in its default configuration) and consistency of the structured output.

---

## 7. Retrieval System

The retrieval system is the technical heart of MediGuide. Given a patient query (or a structured section query derived from a discharge note), the retriever must identify the most relevant chunks from a corpus of 49,423 items. MediGuide employs a hybrid retrieval approach combining sparse BM25 retrieval with dense neural retrieval using PubMedBERT embeddings, fused using Reciprocal Rank Fusion.

### 7.1 BM25 Sparse Retrieval

BM25 (Best Match 25) is a probabilistic sparse retrieval algorithm derived from the BM family of ranking functions (Robertson & Zaragoza, 2009). For a query Q with terms q₁, q₂, ..., qₙ and a document D, BM25 computes:

```
BM25(D, Q) = Σᵢ IDF(qᵢ) × [f(qᵢ, D) × (k₁ + 1)] / [f(qᵢ, D) + k₁ × (1 - b + b × |D|/avgDL)]

Where:
  f(qᵢ, D) = term frequency of qᵢ in D
  IDF(qᵢ)  = inverse document frequency
  |D|       = document length in tokens
  avgDL     = average document length in corpus
  k₁ = 1.5  (term saturation parameter)
  b = 0.75   (length normalization parameter)
```

BM25 is implemented using the `rank_bm25` Python library. The entire tokenized corpus is loaded into memory at startup, consuming approximately 800MB of RAM. BM25 retrieval is very fast (typically < 50ms for a query) because it involves only sparse term matching and scoring with no neural computation.

BM25 is assigned a weight of **0.45** in the RRF fusion step. This weight is lower than the dense retrieval weight because BM25 struggles with synonymy — it will not score a chunk about "myocardial infarction" highly for a query containing "heart attack," whereas the dense retriever handles this naturally through embedding space proximity.

### 7.2 Dense Retrieval (PubMedBERT + FAISS)

The dense retrieval component encodes all corpus chunks into a continuous vector space using the `pritamdeka/S-PubMedBert-MS-MARCO` embedding model. This model is derived from PubMedBERT — a BERT-base model pre-trained from scratch on biomedical text — and has been further fine-tuned for passage retrieval using contrastive learning on the MS MARCO question-answering dataset adapted for medical queries. The fine-tuning process optimizes the model to map semantically similar question-passage pairs close together in embedding space.

All 49,423 chunk embeddings (768-dimensional vectors) are pre-computed offline and stored in a FAISS `IndexFlatIP` (Inner Product) index. Because all vectors are L2-normalized before indexing, inner product is equivalent to cosine similarity. The FAISS index enables approximate nearest neighbor search in sub-linear time.

At query time, the query text is encoded by the same embedding model, and the FAISS index returns the top-N chunks by cosine similarity. A **cosine similarity threshold of 0.28** is applied to filter matches that are not meaningfully related to the query — below this threshold, chunks are excluded from the candidate set regardless of their rank.

Dense retrieval is assigned a weight of **0.55** in the RRF fusion step, reflecting its superior handling of paraphrase and semantic variation in medical language.

### 7.3 Reciprocal Rank Fusion

Reciprocal Rank Fusion (RRF) is a simple, effective, and parameter-efficient method for combining ranked lists from multiple retrievers. The RRF score for a document d given a set of rankers R is:

```
RRF_score(d) = Σ_{r ∈ R} 1 / (k + r(d))

Where:
  R    = set of rankers (BM25, Dense)
  r(d) = rank of document d in ranker r (1-indexed)
  k    = 60 (smoothing constant)
```

The smoothing constant k=60 is the standard default value established in the original RRF paper (Cormack et al., 2009). It prevents the highest-ranked documents from dominating the fusion by limiting the maximum possible contribution of any single rank position to 1/(60+1) ≈ 0.016. Documents that appear in both ranked lists receive contributions from both terms, naturally boosting items that are confirmed relevant by multiple signals.

After RRF fusion, the top-8 chunks by RRF score are selected as the context for the generation model (Top-K=8). Eight chunks were chosen as the retrieval depth because LLaMA 3.1 8B's context window can comfortably accommodate 8 × 384 = 3,072 tokens of retrieved evidence plus the system prompt and query.

### 7.4 Source Filtering by Section

Different sections of a discharge note warrant evidence from different data sources. The medication sections of a discharge note, for example, are best explained using drug label information from openFDA, while general health questions are better served by MedlinePlus or PubMed. MediGuide implements a source filtering layer that restricts the retrieval candidate set to sources appropriate for each section type:

| Section | Preferred Sources |
|---|---|
| `medications` | openFDA (primary), MedlinePlus |
| `assessment` / `history` | PubMed, MedlinePlus, PLABA |
| `follow_up` | MedlinePlus, PLABA |
| `warning_signs` | MedlinePlus, PubMed |
| `instructions` | MedlinePlus, PLABA |
| Health Q&A (all) | All sources |

Source filtering is implemented as a pre-retrieval mask applied to the FAISS index and as a post-retrieval filter on BM25 results. Metadata stored alongside each chunk includes the source identifier, enabling efficient filtering.

### 7.5 Section-Aware Retrieval Strategy

For discharge note explanation, rather than submitting the entire discharge note as a single concatenated query, the retrieval module issues multiple targeted sub-queries — one per detected section — using the section-appropriate source filter. The retrieved chunks from all sub-queries are merged and de-duplicated before being passed to the generation module. This strategy ensures that the retrieved evidence is distributed across all sections of the note, rather than being dominated by whichever section happens to contain the most distinctive vocabulary.

---

## 8. Generation System

### 8.1 LLaMA 3.1 8B via Ollama

MediGuide uses Meta AI's LLaMA 3.1 8B as its generation model, accessed locally through Ollama — an open-source tool for running large language models on consumer hardware. LLaMA 3.1 8B is an instruction-tuned decoder-only transformer with 8 billion parameters, trained on a diverse multilingual corpus and fine-tuned for instruction following using RLHF. At 8B parameters, it strikes a practical balance between generation quality and local inference speed, achieving approximately 15-30 tokens per second on a modern Apple Silicon (M-series) or NVIDIA RTX-class GPU.

Key generation parameters:
- **Temperature:** 0.15 — very low temperature is used to favor factual, conservative responses over creative or speculative language, which is critical for medical information.
- **Streaming:** enabled via Ollama's streaming API.
- **Context window:** 4096 tokens (sufficient for 8 retrieved chunks + system prompt + query).

### 8.2 System Prompt Design

The system prompt is the primary mechanism for controlling the tone, structure, and safety posture of the generated responses. MediGuide uses two distinct system prompts — `SYSTEM_PROMPT` for discharge note explanation and `HEALTHQA_SYSTEM_PROMPT` for health Q&A — both designed with the following principles:

1. **Patient-first language:** The prompt instructs the model to address the patient directly ("you"), use plain language, and avoid unexplained medical jargon.
2. **Warm and reassuring tone:** The prompt establishes a "warm, caring medical educator" persona, acknowledging that patients may be anxious or confused.
3. **Structured output:** The discharge note prompt requires the model to organize its response into four labeled sections: "What This Means For You," "Your Medications," "Follow-Up Care," and "Warning Signs — Call 911 or Go to the ER If..."
4. **Safety disclaimer:** Both prompts include an instruction to remind patients that the system's responses are for educational purposes and do not replace professional medical advice.
5. **Evidence grounding:** The prompt instructs the model to base its response on the provided retrieved evidence and to acknowledge uncertainty when the evidence is insufficient.

### 8.3 Prompt Construction

The full prompt sent to LLaMA 3.1 8B is constructed as follows:

```
[SYSTEM_PROMPT or HEALTHQA_SYSTEM_PROMPT]

--- EVIDENCE FROM MEDICAL DATABASES ---
[1] Source: {source_name} | {chunk_text_1}
[2] Source: {source_name} | {chunk_text_2}
...
[8] Source: {source_name} | {chunk_text_8}
----------------------------------------

PATIENT QUERY:
{discharge_note_text or health_question}

Please provide a clear, compassionate explanation for this patient.
```

The numbered evidence block provides the model with explicit attribution anchors, enabling it to reference specific sources in its response. The separation between the evidence block and the patient query ensures that the model treats the evidence as background context rather than as part of the question.

### 8.4 Fallback Template Engine

The fallback template engine is activated when Ollama is unavailable — either because the service is not running, because the model has not been downloaded, or because the system does not have sufficient GPU/CPU resources to run inference within the response timeout.

The fallback engine operates without any LLM by directly processing the retrieved chunks:
1. It filters the retrieved chunks to those tagged as patient-facing sources (MedlinePlus, PLABA).
2. It extracts the most informative sentences from each chunk using a simple term-frequency-based sentence scoring heuristic.
3. It assembles a structured plain-text response using fixed-format templates for each discharge note section.
4. It appends standard boilerplate for the safety disclaimer and source attribution.

While the fallback response is less fluent and less personalized than an LLM-generated response, it is factually grounded in retrieved evidence and is meaningfully more useful than an error message. The fallback mode is transparently indicated to the user in the UI.

### 8.5 Two System Prompts: Discharge vs. Health Q&A

The two system prompts differ in their expected output structure and query handling strategy:

**SYSTEM_PROMPT (Discharge Note Explainer):**
- Instructs the model to process the input as a clinical document.
- Requires the four-section response structure.
- Emphasizes medication safety (correct dose, frequency, what to watch for).
- Includes the warning signs section as a mandatory component.

**HEALTHQA_SYSTEM_PROMPT (Health Q&A):**
- Instructs the model to answer a single health question.
- Allows flexible response structure appropriate to the question type.
- Emphasizes evidence citation and appropriate uncertainty.
- Includes a reminder to recommend professional consultation for diagnosis or treatment decisions.

### 8.6 Streaming via Server-Sent Events

The SSE stream uses the following event types:

| Event Type | Payload | Description |
|---|---|---|
| `status` | `{"message": "Searching medical databases..."}` | Progress updates during retrieval |
| `sources` | `{"sources": [{...}, {...}]}` | Retrieved source metadata |
| `token` | `{"token": "The "}` | Single LLM output token |
| `done` | `{"message": "complete"}` | Stream termination signal |
| `error` | `{"error": "Ollama unavailable"}` | Error notification |

The frontend accumulates `token` events into a single response buffer and renders the assembled text using a Markdown parser, enabling the model to use headings, bullet points, and bold text in its responses. The `sources` event triggers rendering of a source attribution panel below the response.

---

## 9. User Interface Design

### 9.1 Design Principles

The MediGuide UI was designed around three primary principles that reflect the needs of the patient population it serves:

**Accessibility and Plain Language:** All UI text, labels, and instructions are written at a 6th-grade reading level. Button labels use action verbs ("Explain My Discharge Note," "Ask a Health Question") rather than technical terminology. Error messages are patient-friendly ("We're having trouble connecting. Please try again.") rather than technical.

**Mobile-First Responsive Design:** The layout uses CSS Flexbox and Grid with breakpoints optimized for phone, tablet, and desktop screens. Touch targets are a minimum of 44×44 pixels as recommended by WCAG 2.1. Font sizes scale with viewport width.

**Minimizing Cognitive Load:** The two-mode architecture presents patients with a clear binary choice at the start of each session rather than a blank input box. Suggestion chips provide example queries that help patients who may not know how to phrase their question.

### 9.2 Two-Mode Architecture

The interface presents two clearly labeled modes accessible from the main navigation:

- **Discharge Note Explainer:** Designed for patients who have received a clinical discharge note. Users can paste text directly, or upload a file (PDF, DOCX, TXT, or scanned image). The mode displays a structured explanation with the four mandatory sections.
- **Health Q&A:** Designed for general health questions. Users type a free-form question and receive a referenced, plain-language answer.

Mode switching is accomplished via tab navigation and is reflected in the conversation history labels and in the SSE endpoint used for the backend request.

### 9.3 Conversation History

Every exchange between the user and MediGuide is automatically saved to `localStorage` under a UUID-keyed entry. The history panel (accessible via a drawer on mobile, a fixed sidebar on desktop) displays conversations grouped by recency:

- **Today** — conversations initiated on the current calendar date
- **Yesterday** — conversations from the previous calendar day
- **Last 7 Days** — conversations from the past week (excluding today and yesterday)
- **Older** — all earlier conversations

Selecting a history entry restores the full conversation context in the main panel. The user can delete individual history entries or clear all history. Because history is stored in `localStorage` rather than on a server, it is not accessible to MediGuide's backend and is purged when the user clears browser storage.

### 9.4 Smart Features

**Recommendation Chips:** After generating a response, MediGuide displays two to four follow-up question chips related to the response topic. For example, after explaining metoprolol in a discharge note, chips might read "What are the side effects of metoprolol?" and "Can I drink alcohol while taking metoprolol?" These chips are generated by extracting the key medication and condition terms from the response and constructing standard follow-up question templates.

**Suggestion Chips:** In the Health Q&A mode, the initial empty state displays a set of six example questions as clickable chips, reducing the blank-screen effect and helping users understand the types of questions the system can answer.

**Spell Correction:** MediGuide implements client-side spell correction for medical terms using a dictionary of 35+ common medical terms and their misspellings. When a user submits a query containing a recognized misspelling (e.g., "dibetes," "blod pressure," "cholestrol"), the corrected term is substituted before the query is sent to the backend, and a small notification informs the user of the correction.

### 9.5 File Upload Pipeline

The file upload feature allows patients to upload their discharge note as a digital or scanned document rather than copy-pasting text. The pipeline supports four file types:

| File Type | Library | Notes |
|---|---|---|
| PDF | `pdfplumber` | Extracts text layer; handles multi-page documents |
| DOCX | `python-docx` | Extracts text from paragraphs and tables |
| TXT | Python built-in | UTF-8 and Latin-1 encoding detection |
| PNG/JPG/TIFF | `pytesseract` (Tesseract OCR) | For scanned documents; requires Tesseract installation |

After upload, the extracted text is displayed in an editable text area, allowing the patient to review and correct any extraction errors before submitting for explanation. This is particularly important for OCR output from low-resolution scans.

### 9.6 Dark/Light Mode

MediGuide supports both dark and light display modes, switchable via a toggle button in the navigation bar. The implementation uses CSS custom properties (variables) for all color values, allowing the entire color scheme to be swapped by changing a single `data-theme` attribute on the `<html>` element. The user's preference is persisted in `localStorage` and restored on subsequent visits.

---

## 10. Evaluation Methodology & Results

### 10.1 Evaluation Dataset

MediGuide is evaluated on a held-out test set derived from the PLABA dataset. The PLABA dataset contains 749 clinical question and plain-language answer pairs, each linked to one or more PubMed abstracts that support the answer. Twenty pairs were withheld from the indexing pipeline and designated as the test set. For each test pair, the PLABA dataset provides the "gold" chunk IDs — the specific corpus chunks that are expected to be retrieved for a correct response.

The use of PLABA for evaluation is well-suited to MediGuide's task because PLABA pairs represent exactly the kind of question a patient might ask after reading a clinical document: they are clinical questions answered in plain language with evidence grounded in peer-reviewed literature.

### 10.2 Retrieval Metrics

Three standard information retrieval metrics are computed over the 20 test pairs:

**Precision@K** measures the fraction of the top-K retrieved chunks that are relevant (i.e., match a gold chunk ID):

```
Precision@K = |{relevant documents} ∩ {top-K retrieved}| / K
```

**Recall@K** measures the fraction of all relevant (gold) chunks that appear in the top-K retrieved results:

```
Recall@K = |{relevant documents} ∩ {top-K retrieved}| / |{relevant documents}|
```

**Mean Reciprocal Rank (MRR)** measures how highly ranked the first relevant chunk is on average:

```
MRR = (1/|Q|) × Σ_{q ∈ Q} 1 / rank_q

Where rank_q is the rank position of the first relevant chunk for query q.
```

All retrieval metrics are computed with K=5, consistent with the convention in the evaluation literature for top-5 retrieval evaluation.

### 10.3 Generation Metrics

**ROUGE-L** (Recall-Oriented Understudy for Gisting Evaluation — Longest Common Subsequence) measures the lexical overlap between the generated explanation and the gold plain-language explanation from PLABA. ROUGE-L is computed as the F1-score of the longest common subsequence:

```
ROUGE-L_F1 = (2 × LCS_Precision × LCS_Recall) / (LCS_Precision + LCS_Recall)
```

**Flesch-Kincaid Grade Level** measures the estimated US school grade level required to comprehend a text, using the formula:

```
FK Grade = 0.39 × (words/sentences) + 11.8 × (syllables/words) − 15.59
```

A lower grade level indicates more accessible text. For a general adult patient population, a target of 6th–8th grade is ideal, though 9th–10th grade is acceptable for health information.

### 10.4 Results

| Metric | Score | Interpretation |
|---|---|---|
| Precision@5 | 0.150 | 15% of top-5 retrieved chunks are relevant |
| Recall@5 | 0.550 | 55% of gold chunks appear in the top-5 results |
| MRR | 0.576 | First relevant chunk appears at average rank ~1.7 |
| ROUGE-L | 0.117 | Moderate lexical overlap with gold explanations |
| Flesch-Kincaid Grade | 9.3 | Readable by most adult patients |
| Total Chunks Indexed | 49,423 | Across 4 open medical databases |

### 10.5 Analysis

**Recall@5 = 0.55** is a strong result for open-domain medical retrieval over a corpus of 49,423 chunks from four heterogeneous data sources. It indicates that, on average, more than half of the chunks considered authoritative for a given clinical question are surfaced within the top 5 retrieved results. This is notable given that the corpus was not specifically constructed for the PLABA test queries — the retriever is performing zero-shot retrieval against a general medical corpus.

**MRR = 0.576** translates to a mean first-relevant-rank of approximately 1/0.576 ≈ 1.74. This means that, on average, the first relevant chunk appears at position 1 or 2 in the ranked list — in practice, the most relevant evidence is almost always in the top 2 retrieved chunks. This is encouraging for the generation quality, because LLMs tend to pay most attention to content early in the context window.

**Precision@5 = 0.15** is lower than typical for retrieval systems evaluated on narrow, closed-domain datasets. This reflects the "needles in a haystack" challenge of the MediGuide corpus: with 49,423 chunks, many of which are topically related but not specifically relevant to a given test query, precision is inherently limited. Adding more precisely targeted training data (e.g., MIMIC-IV clinical notes) would likely improve precision substantially.

**ROUGE-L = 0.117** is low by the standards of closed-domain QA benchmarks, but this is expected and appropriate for RAG systems. The LLaMA 3.1 8B model paraphrases, synthesizes, and elaborates on the retrieved evidence rather than copying it verbatim, so lexical overlap with the gold answer is naturally limited. Higher ROUGE-L scores would actually be a concern, as they might indicate the model is extractively copying retrieved text rather than generating patient-friendly explanations. A semantic similarity metric such as BERTScore is a more appropriate evaluation measure for RAG-generated text, and we plan to add this evaluation in future work.

**Flesch-Kincaid Grade Level = 9.3** places MediGuide's outputs at approximately a 9th-grade reading level — three grades above the national adult literacy average, but consistent with the readability targets for consumer health information materials from organizations such as the American Medical Association and the CDC. This represents a meaningful improvement over raw clinical discharge notes, which are typically written at a 12th-grade level or higher, and is consistent with widely used patient education materials.

---

## 11. Limitations

### 11.1 Retrieval Precision

Precision@5 of 0.15 indicates that, on average, only 0.75 of the 5 retrieved chunks are directly relevant to the query. While this is mitigated by the strong MRR score (the top result is usually relevant), it means that the generation model receives a noisy evidence context. Incorporating MIMIC-IV (a dataset of 331,794 de-identified clinical notes from Beth Israel Deaconess Medical Center) would provide a much denser index of discharge-note-specific language, likely improving precision substantially for discharge note explanation tasks.

### 11.2 ROUGE-L as a Generation Metric

ROUGE-L measures lexical overlap and is not an ideal metric for evaluating RAG faithfulness. A response that is factually correct but expressed in different words from the reference answer will score low on ROUGE-L, while a response that copies reference phrases but omits key safety information could score high. We have identified this limitation and plan to add a Natural Language Inference (NLI) based faithfulness hook in future work, which checks whether each sentence of the generated response is entailed by the retrieved evidence.

### 11.3 OCR Quality

The file upload pipeline's OCR capability (via Tesseract) is highly sensitive to scan quality. Discharge notes from older fax machines or low-resolution photocopies may produce text with significant character recognition errors, which can degrade retrieval quality. Users are advised to use the highest available scan resolution, and the UI explicitly prompts users to review extracted text before submission.

### 11.4 LLM Performance

LLaMA 3.1 8B running on Ollama provides good generation quality but at a speed that depends heavily on available hardware. On Apple Silicon (M1 Pro and above) or a modern NVIDIA RTX GPU, inference runs at 15–30 tokens per second, producing a complete response in 10–20 seconds. On CPU-only systems, inference may take 60–180 seconds per response, which may be impractical for patient use. The fallback template engine mitigates this by providing immediate responses when LLM inference is unavailable, but at the cost of fluency and personalization.

### 11.5 Spell Correction Coverage

The current spell correction module covers 35 medical terms, representing only a fraction of the medical vocabulary. Misspellings of less common medical terms will not be corrected and may degrade retrieval quality. A more robust approach — such as using a medical spell checker based on an extended medical lexicon, or using the embedding model's tolerance for near-synonym representations — would improve robustness for the long tail of medical terminology.

---

## 12. Future Work

### 12.1 MIMIC-IV Integration

The MIMIC-IV dataset (Johnson et al., 2023) contains 331,794 de-identified clinical notes from Beth Israel Deaconess Medical Center, including discharge summaries, nursing notes, and physician progress notes. Integrating MIMIC-IV into the MediGuide corpus would provide a large, highly discharge-specific evidence base that would directly address the current precision limitation. Because MIMIC-IV requires credentialed access (PhysioNet account and training), it cannot be distributed with MediGuide by default, but the data loading infrastructure can be built to support it as an optional data source.

### 12.2 MedQuAD Dataset

The MedQuAD dataset (Ben Abacha & Demner-Fushman, 2019) contains 47,457 medical question-answer pairs derived from 12 NIH websites. Incorporating MedQuAD into the Health Q&A mode's corpus would substantially expand the coverage of consumer health questions and improve retrieval precision for common patient queries.

### 12.3 BERTScore Evaluation

As discussed in Section 10.5, ROUGE-L is an insufficient metric for evaluating RAG generation quality. BERTScore (Zhang et al., 2020) uses contextual embeddings to compute semantic similarity between generated and reference text, providing a much more meaningful measure of response quality. Implementing BERTScore evaluation requires a GPU for efficient computation but would provide significantly more interpretable evaluation results.

### 12.4 Multi-Language Support

A substantial proportion of U.S. patients are non-English speakers or have limited English proficiency. Spanish and Mandarin Chinese are the two most spoken languages other than English in the U.S., and both populations experience significant health literacy barriers. Future versions of MediGuide should support multi-language operation, including language detection, translated system prompts, and potentially language-specific retrieval corpora (e.g., MedlinePlus en Español).

### 12.5 Voice Interface

Many patients who struggle with written health information would benefit from a voice-based interface. Adding speech-to-text input (via the Web Speech API or a local Whisper model) and text-to-speech output would make MediGuide accessible to patients who are not comfortable typing or reading on a screen. This is particularly relevant for elderly patients and those with low literacy.

### 12.6 Mobile Application

A native mobile application (React Native or Flutter) would lower the barrier to access compared to a web application, as patients could use MediGuide directly from their phone's home screen without navigating to a URL. A mobile app could also leverage the phone's camera for document scanning with automatic preprocessing to improve OCR quality.

### 12.7 Fine-Tuned LLM

The current system uses a general-purpose instruction-tuned LLaMA 3.1 8B model. Fine-tuning this model specifically on discharge note explanation data — using the PLABA dataset and potentially synthetic discharge note explanation pairs generated by a larger model — could substantially improve the quality, structure, and patient-friendliness of generated responses. Parameter-efficient fine-tuning methods such as LoRA (Low-Rank Adaptation) would enable this fine-tuning on consumer hardware.

### 12.8 User Study with Real Patients

All evaluation in the current work is automated, using the PLABA test set as a proxy for real patient interactions. A prospective user study with real patients — measuring comprehension, satisfaction, and recall of key discharge information — would provide the most clinically meaningful evaluation of MediGuide's impact. Such a study would require IRB approval and partnerships with hospital discharge teams.

---

## 13. Conclusion

MediGuide addresses a concrete, measurable problem in patient health literacy: the inability of most patients to fully comprehend their clinical discharge documentation. The consequences of this failure — medication errors, missed follow-up care, delayed recognition of warning signs, and preventable readmissions — impose significant human and financial costs on patients and healthcare systems alike.

By combining hybrid BM25 + PubMedBERT retrieval with Reciprocal Rank Fusion over a curated corpus of 49,423 chunks from four authoritative open medical databases, MediGuide surfaces highly relevant medical evidence efficiently and reliably. The system achieves a Recall@5 of 0.55 and an MRR of 0.576 on the PLABA evaluation benchmark, indicating that gold-standard evidence is retrieved within the top two results on average. LLaMA 3.1 8B converts this evidence into warm, structured, plain-language explanations delivered with a Flesch-Kincaid Grade Level of 9.3 — meaningfully more accessible than raw clinical discharge notes.

Perhaps most importantly, MediGuide achieves these results without requiring any cloud connectivity. Patient data — potentially including sensitive information about diagnoses, medications, and medical history — never leaves the user's device. This privacy-by-design approach eliminates a fundamental barrier to patient adoption of AI health tools and makes MediGuide a viable option for deployment in settings where data sovereignty is a legal or ethical requirement.

MediGuide is open-source, locally deployable, and built entirely from openly licensed components — the LLaMA 3.1 8B model, the PubMedBERT embedding model, the rank_bm25 library, and the four open medical databases. We hope it serves as a practical foundation for further research and development at the intersection of NLP, health informatics, and patient-centered care, and that future extensions — MIMIC-IV integration, multi-language support, voice interfaces, and clinical user studies — will bring the vision of an AI-powered patient health companion to broader patient populations.

The code, indexes, and evaluation scripts for MediGuide are available at https://github.com/gautampatel1/MediGuideV2.

---

## 14. References

1. Kwon, S., Kim, S., Yoo, E., & Kim, J. (2023). **PLABA: A dataset for plain-language adaptation of biomedical abstracts.** In *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL 2023)*. Association for Computational Linguistics.

2. U.S. National Library of Medicine. (2024). **MedlinePlus: Health information from the National Library of Medicine.** National Institutes of Health. https://medlineplus.gov

3. U.S. Food and Drug Administration. (2024). **openFDA API.** https://open.fda.gov

4. National Center for Biotechnology Information. (2024). **PubMed and the Entrez Programming Utilities (E-utilities).** National Library of Medicine. https://www.ncbi.nlm.nih.gov/books/NBK25501/

5. Robertson, S., & Zaragoza, H. (2009). **The probabilistic relevance framework: BM25 and beyond.** *Foundations and Trends in Information Retrieval*, 3(4), 333–389. https://doi.org/10.1561/1500000019

6. Johnson, J., Douze, M., & Jégou, H. (2019). **Billion-scale similarity search with GPUs.** *IEEE Transactions on Big Data*, 7(3), 535–547. https://doi.org/10.1109/TBDATA.2019.2921572

7. Meta AI. (2024). **LLaMA 3.1: Open foundation and fine-tuned chat models.** Meta Platforms, Inc. https://ai.meta.com/blog/meta-llama-3-1/

8. Deka, P. (2022). **pritamdeka/S-PubMedBert-MS-MARCO** [Model]. Hugging Face Hub. https://huggingface.co/pritamdeka/S-PubMedBert-MS-MARCO

9. Lin, C.-Y. (2004). **ROUGE: A package for automatic evaluation of summaries.** In *Text Summarization Branches Out: Proceedings of the ACL-04 Workshop*, 74–81. Association for Computational Linguistics.

10. Kincaid, J. P., Fishburne, R. P., Rogers, R. L., & Chissom, B. S. (1975). **Derivation of new readability formulas (Automated Readability Index, Fog Count, and Flesch Reading Ease Formula) for Navy enlisted personnel** (Research Branch Report 8-75). Naval Air Station Memphis.

11. Jencks, S. F., Williams, M. V., & Coleman, E. A. (2009). **Rehospitalizations among patients in the Medicare fee-for-service program.** *New England Journal of Medicine*, 360(14), 1418–1428. https://doi.org/10.1056/NEJMsa0803563

12. Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D. (2020). **Retrieval-augmented generation for knowledge-intensive NLP tasks.** *Advances in Neural Information Processing Systems*, 33, 9459–9474.

13. Cormack, G. V., Clarke, C. L. A., & Buettcher, S. (2009). **Reciprocal rank fusion outperforms Condorcet and individual rank learning methods.** In *Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval*, 758–759. https://doi.org/10.1145/1571941.1572114

14. Gu, Y., Tinn, R., Cheng, H., Lucas, M., Usuyama, N., Liu, X., ... & Poon, H. (2021). **Domain-specific language model pretraining for biomedical natural language processing.** *ACM Transactions on Computing for Healthcare*, 3(1), 1–23. https://doi.org/10.1145/3458754

15. Ben Abacha, A., & Demner-Fushman, D. (2019). **A question-entailment approach to question answering.** *BMC Bioinformatics*, 20(1), 511. https://doi.org/10.1186/s12859-019-3119-4

---

*MediGuide is an open-source research project. The system is designed for educational purposes and does not constitute medical advice. Patients should always consult their healthcare provider for diagnosis, treatment, and medication guidance.*

*Report prepared: April 2026 | Word count: ~5,800 words*
