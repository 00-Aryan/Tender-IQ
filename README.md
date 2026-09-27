# TenderIQ

AI-powered vehicle tender intelligence assistant for GeM portal tenders.

TenderIQ helps users understand complex GeM tender PDFs through document-grounded question answering.

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

The answer prompt requires responses to use the uploaded document and not claim official eligibility. Citation selection is a known limitation described below.

---

## What Is Actually Built (Current State)

| Component | Status | Notes |
|---|---|---|
| PDF to markdown extraction | Done | `pymupdf4llm.to_markdown(page_chunks=True)` converts the full PDF and adds page markers |
| Regex structured extraction | Done | `reg_ex_parser.py` extracts a limited set of bid, date, financial, fleet, and duration fields from the first six pages |
| Structure-based chunking | Done | MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter, 1200-character chunks with 100-character overlap |
| ChromaDB vector storage | Done | Local, persisted, filtered by tender_id |
| HuggingFace embeddings | Done | all-MiniLM-L6-v2, CPU, lazy loaded |
| LangChain RAG chain | Done | LCEL pipeline, query expansion, BM25 + MMR retrieval, Gemini |
| FastAPI backend | Done | Upload, background processing status, specifications, and chat routes |
| SQLite persistence | Done | SQLAlchemy stores processing status and serialized tender specifications |
| Pydantic schema (TenderRequirements) | Done | Financials, eligibility, fleet, documents, dates, compliance |
| Pydantic schema (UserProfile) | Done | Vehicle info, work orders, documents, turnover |
| Structured extraction chain | Prototype | PydanticOutputParser experiment exists; active ingestion uses regex extraction |
| Provider-agnostic LLM config | Partial | Gemini and OpenAI/OpenRouter configurations exist; the active model factory initializes Gemini |
| Streamlit UI | Done | Upload + RAG chat, minimal |
| Conversation memory | Not built | Each question is independent |
| Eligibility matching engine | Not built | UserProfile exists, but no matcher consumes it |
| LangGraph agent orchestration | Not built | No LangGraph dependency or implementation |
| Structured logging | Not built | Runtime diagnostics currently use print() |
| Deployment | Not done | Streamlit Cloud planned |

The structured LLM extractor under `src/tender_iq/extraction/scripts/` is experimental. The active ingestion path uses regex extraction; incomplete extraction currently prints a fallback message but does not invoke an LLM fallback.

---

## FastAPI Integration

The Streamlit UI does not call the extraction or RAG modules directly. It expects the FastAPI application to be running at `http://127.0.0.1:8000`.

### Routes

| Method | Route | Behavior |
|---|---|---|
| `POST` | `/api/v1/tenders/upload` | Accepts a PDF upload, creates a `JOB-XXXXXXXX` processing record, saves a temporary file, and schedules background ingestion |
| `GET` | `/api/v1/tenders/{tender_id}/specs` | Returns processing status and extracted specifications; lookup accepts the job ID or GeM bid ID |
| `POST` | `/api/v1/chat/` | Validates a query, runs the chat/RAG service, and returns an answer with citation objects |

`src/tender_iq/main.py` creates the FastAPI application, creates SQLite tables during startup, and registers the routers from `api/v1/endpoints/`. `api/schemas/` contains the Pydantic HTTP contracts. `db/session.py` supplies a request-scoped SQLAlchemy session through FastAPI dependency injection.

The upload endpoint returns HTTP 202 immediately. FastAPI runs `services/ingestion.py::background_process_tender` in the background. The Streamlit processing screen polls the specs route until the status is `completed` or starts with `failed`.

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| UI | Streamlit `>=1.61.1` | Upload, processing polling, chat, and citation display |
| Backend API | FastAPI `>=0.141.1` | Upload, asynchronous ingestion status, specifications, and chat routes |
| Persistence | SQLite + SQLAlchemy `>=2.0.51` | Tender job status and JSON specifications |
| PDF extraction | pymupdf4llm `>=1.27.2.3` + PyMuPDF `>=1.27.2.3` | Full Markdown indexing plus first-six-page plain-text extraction |
| Text splitting | `langchain-text-splitters >=1.1.2` | Header-aware and recursive chunking |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Free, local, no API cost |
| Vector store | ChromaDB via `langchain-chroma >=1.1.0` | Local persisted vector storage |
| Keyword retrieval | BM25 via `rank-bm25 >=0.2.2` | Lexical retrieval combined with vector retrieval |
| LLM | Gemini via `langchain-google-genai >=4.2.7` | Query expansion and answer generation |
| LLM framework | LangChain `>=1.3.12` + LCEL | Chain composition, prompts, retrieval, and output parsing |
| Validation | Pydantic `>=2.13.4` | API and domain schema validation |
| Configuration | python-dotenv `>=1.2.2` | Loads environment variables from `.env` |
| Package manager | uv | Dependency resolution and lockfile management |

Other direct dependencies include `langchain-classic`, `langchain-community`, `langchain-huggingface`, `langchain-openai`, `pandas`, `requests`, `pytest`, `torch`, and `pydantic[email]`. Exact version constraints are maintained in `pyproject.toml`; the project requires Python `>=3.12,<3.13`.

---

## Architecture and Module Interaction

```
Streamlit `app.py`
    → POST `/api/v1/tenders/upload`
    |
FastAPI `main.py` → `api/v1/endpoints/tenders.py`
    → `crud/tenders.py` → SQLite `TenderRecord` with status `processing`
    → FastAPI `BackgroundTasks`
    |
`services/ingestion.py::background_process_tender`
    → `extraction/extract_data.py::process_tender_pdf`
    → `document_processor/loader.py::load_pdf_text` (first 6 pages)
    → `parser/reg_ex_parser.py::parse_with_regex`
    → `models/tender_requirements.py::TenderRequirements`
    |
    → `document_processor/loader.py::load_tender_pdf` (full PDF Markdown)
    → `document_processor/chunker.py::chunk_tender_documents`
    → `vector_store/chroma_store.py::store_tender`
    → ChromaDB with `tender_id`, page, section, subsection, and clause metadata
    → `crud/tenders.py::update_parsed_tender`
    |
Streamlit polls `GET /api/v1/tenders/{tender_id}/specs`
    → stores the real `bid_id` or deterministic document-hash fallback
    |
Streamlit chat
    → POST `/api/v1/chat/`
    → `services/chat.py::process_chat_query`
    → SQLite lookup through `crud/tenders.py::get_tender_by_id`
    → Chroma document lookup through `get_all_chunks_for_tender`
    → `rag/tender_rag.py::build_rag_chain`
    → `rag/query_transformers.py::build_multi_query_retrieval_chain`
    → query expansion through `prompts/query_expansion_prompt.py`
    → BM25 + filtered MMR retrieval
    → `prompts/rag_prompt.py`
    → Gemini through `config/llm_config.py::get_llm`
    → `StrOutputParser`
    → `ChatResponse` from `api/schemas/chat.py`
    → Streamlit answer and citations

### Ingestion details

`background_process_tender` uses two extraction paths for different purposes. The first-six-page plain-text path produces structured `TenderRequirements` data for SQLite. The full Markdown path produces retrieval chunks for ChromaDB. If regex extraction does not find a bid ID, ingestion creates a `DOC_<12-character SHA-256 prefix>` identifier. On failure, the worker stores a `failed: ...` status, deletes the temporary PDF, and closes its database session.

### Chat details

Simple greetings such as `hello`, `thanks`, and `good morning` return a fixed response without database or vector lookup. Other queries retrieve all stored chunks for the tender, build an ensemble retriever, expand the query into multiple variants, deduplicate retrieved documents by content hash, and invoke the answer prompt.

The chat service returns citations from the RAG result's `sources` list, so the displayed sources correspond to the documents passed into the answer prompt.

### Active module map

| Module | Responsibility |
|---|---|
| `app.py` | Streamlit upload, polling, chat state, and API client |
| `main.py` | FastAPI app, startup table creation, and router registration |
| `api/v1/endpoints/` | HTTP route handlers |
| `api/schemas/` | Pydantic request and response contracts |
| `services/ingestion.py` | Background extraction, indexing, persistence, cleanup |
| `services/chat.py` | Greeting handling, tender lookup, RAG invocation, response mapping |
| `document_processor/` | PDF loading, Markdown conversion, page markers, and chunking |
| `extraction/` and `parser/` | Structured extraction orchestration and regex parsing; script subdirectory contains experiments |
| `models/` | Tender requirement and prospective bidder profile models |
| `vector_store/` | Embedding model, Chroma persistence, BM25, MMR, and ensemble retrieval |
| `rag/` | Query expansion, retrieval deduplication, context formatting, and RAG chain construction |
| `prompts/` | Query-expansion, answer-generation, and experimental extraction prompts |
| `config/` | Environment loading, LLM factory, and direct LLM helper |
| `db/` and `crud/` | SQLAlchemy schema/session management and tender record operations |
    |
pymupdf4llm
    → markdown text with preserved table structure
    |
MarkdownHeaderTextSplitter
    → chunks split at clause/section boundaries
    |
RecursiveCharacterTextSplitter
    → long clauses sub-chunked with 100-char overlap
    |
HuggingFace Embeddings (all-MiniLM-L6-v2)
    → 384-dimensional vectors per chunk
    |
ChromaDB (local, persisted)
    → stored with metadata: tender_id, section, subsection
    |
BM25 + MMR ensemble (MMR k=6, filtered by tender_id)
    → diverse relevant chunks retrieved per question
    |
LangChain LCEL RAG Chain
    → query expansion | retrieval | rag_prompt | Gemini | StrOutputParser
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

**Citation source selection**
Page and section metadata are attached to chunks. Chat citations come from the same documents returned by the retrieval chain and used to generate the answer. The response currently exposes the first three retrieved sources.

**Vehicle tender focus**
Extraction fields and prompts focus on vehicle-related tenders, but the upload endpoint accepts any PDF and does not enforce this domain constraint.

**Bilingual tenders**
Some GeM tenders have Hindi and English headers. The repository does not include dedicated bilingual evaluation or language handling.

**Table extraction**
pymupdf4llm is used for Markdown conversion. Experimental table extraction scripts exist, but table accuracy is not covered by the current test suite.

**Eligibility matching**
The system answers questions about eligibility requirements but cannot automatically compare them against a business profile yet. That is the next phase.

**API and runtime dependencies**
The Streamlit UI and FastAPI backend are separate processes. The UI requires the backend to be available at `127.0.0.1:8000`; no authentication or user-level tender isolation is implemented.

---


## Getting Started

```bash
# Clone
git clone https://github.com/00-Aryan/tenderiq.git
cd tenderiq

# Install dependencies (requires uv)
uv sync

# Create a .env file and add the required Gemini configuration.

# Run
uv run streamlit run app.py
```

The FastAPI backend must also be running at `http://127.0.0.1:8000`; Streamlit sends upload, polling, and chat requests to that service.

---

## Planned Improvements

**Phase 2 — Intelligence**
- Conversation memory — multi-turn Q&A with history
- LangGraph eligibility agent — state machine comparing UserProfile against TenderRequirements
- LLM fallback for incomplete regex extraction
- Extraction validation and structured logging
- Correct retrieval-source citation tests and improvements

**Phase 3 — Polish**
- Streamlit Cloud deployment
- Demo video
- pytest suite for eligibility engine

**Future (post-v1)**
- Hindi language support for bilingual tender responses
- Page-level citation alongside section headers
- Tesseract OCR fallback for image-only scanned PDFs
- Pinecone or Qdrant for multi-user vector isolation
- Redis caching for repeated tender queries

---

## Project Status

| Phase | Status |
|---|---|
| Phase 0 — PDF extraction validation | Done |
| Phase 1 — Pydantic schemas | Done |
| Phase 2 — Extraction chain + RAG pipeline | Done |
| Phase 3 — Streamlit UI | Done (minimal) |
| Phase 4 — Eligibility engine | Not built; UserProfile model exists |
| Phase 5 — Memory + logging | Planned |
| Phase 6 — Deployment | Planned |

---

## Tests

The repository currently includes tests for:

- PDF Markdown loading and page markers
- Header-based and page-based chunk metadata
- RAG tender metadata formatting
- FastAPI chat request validation and route response mapping
- Chat citation mapping from RAG source documents

There are no end-to-end tests covering a real PDF upload through background ingestion, Chroma indexing, retrieval, and LLM response generation. Extraction regexes, Chroma persistence, query expansion, and external LLM calls are not covered by live integration tests.

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