# TenderIQ

AI-powered vehicle tender intelligence assistant for GeM portal tenders.

TenderIQ helps small business owners understand complex GeM tender PDFs without needing a consultant or CA.

---

## The Problem

GeM tender documents are dense, legally worded PDFs — often 30–80 pages. Small business owners applying for vehicle-related tenders face:

- Eligibility requirements buried across multiple pages
- Confusion around EMD, security money, and working capital
- Language barriers and technical jargon
- Dependency on consultants charging Rs. 800–1500 per tender
- No way to know if they qualify before spending hours reading

Most users do not know what questions to ask — let alone where to find the answers.

---

## What It Does (v1)

Upload a vehicle tender PDF. Ask questions in plain language. Get grounded answers.

```
What is the EMD amount?             → Extracted directly from document
What vehicles are required?         → Fleet requirements explained
What documents must I submit?       → Document checklist extracted
Explain this clause simply.         → Plain language explanation
What is the working capital needed? → Financial requirements clarified
```

Answers are always grounded in the uploaded document. The system never claims official eligibility — it provides guided reasoning.

---

## What Is Actually Built (Current State)

| Component | Status | Notes |
|---|---|---|
| PDF to markdown extraction | Done | pymupdf4llm — handles text, tables, images |
| Structure-based chunking | Done | MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter |
| ChromaDB vector storage | Done | Local, persisted, filtered by tender_id |
| HuggingFace embeddings | Done | all-MiniLM-L6-v2, CPU, lazy loaded |
| LangChain RAG chain | Done | LCEL pipeline, MMR retrieval, Gemini Flash |
| Pydantic schema (TenderRequirements) | Done | Financials, eligibility, fleet, documents, dates, compliance |
| Pydantic schema (UserProfile) | Done | Vehicle info, work orders, documents, turnover |
| Structured extraction chain | Done | PydanticOutputParser + Gemini Flash |
| Provider-agnostic LLM config | Done | Strategy pattern, runtime model switching |
| Streamlit UI | Done | Upload + RAG chat, minimal |
| Conversation memory | Not built | Each question is independent |
| Eligibility matching engine | Not built | Next phase |
| LangGraph agent orchestration | Not built | Planned for eligibility engine |
| Logging | Not built | Planned |
| Deployment | Not done | Streamlit Cloud planned |

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| UI | Streamlit | Fast iteration, demo-ready |
| PDF extraction | pymupdf4llm | Converts PDF to markdown, handles tables and images |
| Text splitting | LangChain MarkdownHeaderTextSplitter | Respects document clause structure |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Free, local, no API cost |
| Vector store | ChromaDB | Local-first, zero infrastructure |
| LLM | Gemini Flash (free tier) | Fast, capable, zero cost |
| LLM framework | LangChain + LCEL | Chain composition, output parsing |
| Validation | Pydantic v2 | Schema enforcement, type checking |
| Package manager | uv | Fast, reproducible |

---

## Architecture

```
PDF Upload (Streamlit)
    |
pymupdf4llm
    → markdown text with preserved table structure
    |
MarkdownHeaderTextSplitter
    → chunks split at clause/section boundaries
    |
RecursiveCharacterTextSplitter
    → long clauses sub-chunked with 50-char overlap
    |
HuggingFace Embeddings (all-MiniLM-L6-v2)
    → 384-dimensional vectors per chunk
    |
ChromaDB (local, persisted)
    → stored with metadata: tender_id, section, subsection
    |
MMR Retriever (k=4, filtered by tender_id)
    → diverse relevant chunks retrieved per question
    |
LangChain LCEL RAG Chain
    → RunnableParallel(context, question) | rag_prompt | Gemini Flash | StrOutputParser
    |
Plain language answer → Streamlit UI
```

---

## Scope

v1 is intentionally constrained to vehicle-related tenders only:

- LMV (Light Motor Vehicle) tenders
- Logistics vehicle contracts
- Vehicle rental tenders
- Transport support contracts
- Driver and vehicle service tenders

This constraint improves extraction accuracy, reduces hallucinations, and makes the system genuinely useful rather than generically mediocre.

---

## Known Limitations and Tradeoffs

**Conversation memory not implemented**
Each question is answered independently. The system has no memory of previous questions in the same session. Planned for next phase using LangChain RunnableWithMessageHistory.

**Citation shows section header only**
Answers cite the section name but not the page number. Page-based splitting was evaluated and rejected because it breaks semantic meaning for topics that span multiple pages. Accepted tradeoff for v1.

**Vehicle tenders only**
Not designed for civil, IT, or other tender types. Domain constraint is intentional — it improves extraction quality.

**Bilingual tenders**
Some GeM tenders have Hindi and English headers. Retrieval works via English content but section metadata may show Hindi text. No impact on answer quality.

**Table extraction**
pymupdf4llm handles most tables correctly. Complex multi-row tables with merged cells may produce imperfect extraction. Identified and documented during Phase 0 testing.

**Eligibility matching**
The system answers questions about eligibility requirements but cannot automatically compare them against a business profile yet. That is the next phase.

---

## Hardware Requirements

- RAM: minimum 4GB (sentence-transformers loads ~90MB into memory)
- CPU: any modern CPU — no GPU required
- Storage: ChromaDB persists to data/chroma/ — a few MB per tender
- Processing time: 60–120 seconds per tender depending on PDF size and CPU speed
- Internet: required only for Gemini Flash API calls — embeddings run locally

---

## Getting Started

```bash
# Clone
git clone https://github.com/00-Aryan/tenderiq.git
cd tenderiq

# Install dependencies (requires uv)
uv sync

# Add your API key
cp .env.example .env
# Edit .env and add GEMINI_API_KEY=your_key_here

# Run
uv run streamlit run app.py
```

---

## Planned Improvements

**Phase 2 — Intelligence**
- Conversation memory — multi-turn Q&A with history
- LangGraph eligibility agent — state machine comparing UserProfile against TenderRequirements
- Multi-agent extraction validator — Extractor and Validator loop to reduce hallucination
- Logging — every query and extraction logged for prompt improvement

**Phase 3 — Polish**
- Streamlit Cloud deployment
- Demo video
- pytest suite for eligibility engine

**Future (post-v1)**
- Hindi language support for bilingual tender responses
- Page-level citation alongside section headers
- Tesseract OCR fallback for image-only scanned PDFs
- Pinecone or Qdrant for multi-user vector isolation
- FastAPI backend for production API access
- Redis caching for repeated tender queries

---

## Project Status

| Phase | Status |
|---|---|
| Phase 0 — PDF extraction validation | Done |
| Phase 1 — Pydantic schemas | Done |
| Phase 2 — Extraction chain + RAG pipeline | Done |
| Phase 3 — Streamlit UI | Done (minimal) |
| Phase 4 — Eligibility engine | In progress |
| Phase 5 — Memory + logging | Planned |
| Phase 6 — Deployment | Planned |

---

## Portfolio Context

This project demonstrates:

- RAG architecture — chunking strategy, embedding, MMR retrieval, hallucination mitigation
- LangChain LCEL — declarative pipeline composition, output parsing, provider abstraction
- Document intelligence — structured extraction from unstructured legal PDFs
- Pydantic schema design — nested models, validation, type enforcement
- System design thinking — constrained intelligence over broad intelligence, conscious tradeoffs

---

## Author

Aryan Kumar
Final Year B.S. Data Science and Applications — IIT Madras

GitHub: https://github.com/00-Aryan
LinkedIn: https://linkedin.com/in/aryan-kumar-1969b819b/