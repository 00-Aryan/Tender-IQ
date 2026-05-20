# TenderIQ 

> **AI-powered vehicle tender intelligence assistant for GeM portal tenders**

TenderIQ helps small business owners and vehicle operators understand, evaluate, and discuss complex GeM tender PDFs — without needing a consultant.

---

## The Problem

GeM tender documents are dense, legally worded PDFs — often 30–80 pages. Small business owners applying for vehicle-related tenders face:

- Unclear eligibility requirements buried across multiple pages
- Confusion around EMD, security money, and working capital
- Language barriers and technical jargon
- Dependency on consultants charging ₹800–1500 per tender
- No way to know if they qualify before investing hours of effort

**Most users don't know what questions to ask — let alone where to find the answers.**

---

## The Solution

TenderIQ is a document intelligence and decision-support assistant focused specifically on **vehicle-related GeM tenders** (LMV, logistics, vehicle rental, transport contracts).

Upload a tender PDF. Get clarity.

```
What documents do I need?       → Clear answer
Am I eligible?                  → Estimated match with reasoning
What is the EMD amount?         → Extracted directly from document
Explain this clause simply.     → Plain language explanation
What working capital is needed? → Extracted and explained
```

---

## Key Features (v1)

- **PDF Upload & Processing** — Handles selectable PDFs and scanned PDFs (OCR fallback)
- **Tender Explanation** — Ask any question about the tender in plain language
- **Eligibility Matching** — Compare your business profile against tender requirements
- **Conversational Assistant** — Follow-up questions with full tender context maintained
- **Structured Extraction** — Key fields extracted into a clean, readable format
- **Logging & Feedback** — Every interaction logged for continuous improvement

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| UI | Streamlit | Fast iteration, easy demo |
| Backend | FastAPI | Async, auto-docs, production-ready |
| PDF Extraction | PyMuPDF | Fast, accurate text extraction |
| OCR Fallback | Tesseract | Free, local, handles scanned PDFs |
| Embeddings | sentence-transformers | Free, local, no API cost |
| Vector Store | ChromaDB | Local-first, zero infra |
| LLM | Gemini Flash (Free Tier) | Fast, capable, zero cost |
| Database | SQLite | Simple, local, no setup |
| Validation | Pydantic v2 | Schema enforcement |

---

## Architecture

```
PDF Upload
    ↓
Document Classification
    ↓
PyMuPDF Extraction → OCR Fallback (if scanned)
    ↓
Text Cleanup & Chunking
    ↓
Embedding & ChromaDB Storage
    ↓
Structured Extraction Agent (vehicle tender schema)
    ↓
Validator Agent (checks extraction quality)
    ↓
Eligibility Matching Engine
    ↓
Conversational RAG Layer (Gemini Flash)
    ↓
Human-readable Explanation → Streamlit UI
```

---

## Scope

**v1 is intentionally constrained to vehicle-related tenders only:**

- LMV (Light Motor Vehicle) tenders
- Logistics vehicle contracts
- Vehicle rental tenders
- Transport support contracts
- Driver + vehicle service tenders

This constraint improves extraction accuracy, reduces hallucinations, and makes the system genuinely useful rather than generically mediocre.

---

## Accuracy Philosophy

TenderIQ v1 does **not** guarantee official legal eligibility. It provides:

- Guided reasoning
- Estimated matching with explanation
- Transparent uncertainty

```
✅ "Based on your profile, you likely satisfy the experience requirement because..."
❌ "You are officially eligible."
```

---

## Getting Started

```bash
# Clone the repo
git clone https://github.com/00-Aryan/tenderiq.git
cd tenderiq

# Install dependencies
pip install -r requirements.txt

# Add your API key
cp .env.example .env
# Add GEMINI_API_KEY to .env

# Run the app
streamlit run app.py
```

---

## Project Status

| Phase | Status | Description |
|---|---|---|
| Phase 0 | 🔄 In Progress | FastAPI + PDF extraction fundamentals |
| Phase 1 | ⏳ Planned | Core pipeline — extraction, RAG, matching |
| Phase 2 | ⏳ Planned | History, logging, evaluation |
| Phase 3 | ⏳ Planned | Polish, deployment, demo |

---

## Portfolio Context

This project demonstrates:

- **Document Intelligence** — structured extraction from unstructured PDFs
- **RAG Architecture** — retrieval-augmented generation with domain constraints
- **LLM Orchestration** — multi-agent extraction with validation loops
- **Backend Engineering** — FastAPI, SQLAlchemy, Pydantic
- **System Design Thinking** — constrained intelligence over broad intelligence

---

## Author

**Aryan Kumar**
Final Year B.S. Data Science & Applications — IIT Madras

[![GitHub](https://img.shields.io/badge/GitHub-00--Aryan-black)](https://github.com/00-Aryan)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Aryan%20Kumar-blue)](https://linkedin.com/in/aryan-kumar-1969b819b/)

---

*TenderIQ v1 — Built for real-world utility and portfolio depth*