# TenderIQ

> A document-grounded intelligence assistant that turns GeM vehicle tender PDFs into searchable, explainable answers for small businesses.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/Orchestration-LangChain-1C3C3C)](https://www.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/Retrieval-ChromaDB-F5A623)](https://www.trychroma.com/)
[![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)

## The Problem

GeM tender PDFs bury deadlines, EMD requirements, fleet specifications, eligibility clauses, and document checklists across dense legal and technical language. A bidder should not need to read an 80-page document line by line, or trust an answer that cannot point back to the source.

## The Solution

TenderIQ provides a focused workflow:

1. Upload a vehicle tender PDF through Streamlit.
2. Extract structured bid fields and index the full document.
3. Ask questions in plain language.
4. Retrieve relevant tender sections and generate a grounded answer with source snippets.

The system is deliberately scoped to vehicle-related tenders and instructs the LLM not to invent facts or claim official eligibility.

## Engineering Highlights

### Hybrid retrieval for legal documents

Tender language contains both exact procurement terms and semantic variations. TenderIQ combines:

- **BM25 lexical retrieval** for exact terms such as `Bid End Date/Time` and `EMD Amount`.
- **ChromaDB vector retrieval** using `all-MiniLM-L6-v2` embeddings and filtered MMR search.
- **Weighted ensemble ranking** with BM25/vector weights of `0.4/0.6`.
- **Multi-query expansion** that generates alternative procurement phrasings before batch retrieval.
- **Content-hash deduplication** so overlapping query results do not duplicate context.

This is implemented with LangChain's `EnsembleRetriever`; the repository does not currently implement literal Reciprocal Rank Fusion (RRF).

### Token-conscious intent gating

Simple greetings and polite phrases are recognized before database, retrieval, query-expansion, or answer-generation work begins. They receive a deterministic response, avoiding unnecessary model calls and retrieval cost for non-document questions.

### Decoupled asynchronous ingestion

The Streamlit frontend is an HTTP client, not the pipeline runtime. FastAPI accepts an upload, persists a processing record in SQLite, schedules an in-process `BackgroundTasks` job, and returns HTTP 202 immediately. Streamlit polls the job status while the backend performs extraction, chunking, embedding, Chroma indexing, and persistence.

### Dual-purpose document processing

The ingestion path intentionally uses two representations:

- The first six PDF pages are plain-text extracted and parsed with regex into a typed `TenderRequirements` model.
- The full PDF is converted to Markdown with page markers, structurally chunked, and indexed for retrieval.

This keeps structured metadata fast and predictable while preserving the full document for question answering.

## Architecture

```text
                         Upload / Chat HTTP
Streamlit app.py ------------------------------------+
                                                      |
                         FastAPI main.py              v
                   +--------------------+     API routers
                   | SQLite TenderRecord|<---- CRUD layer
                   +--------------------+
                              |
                    BackgroundTasks (202)
                              v
                      services/ingestion.py
                              |
        +---------------------+----------------------+
        |                                            |
  First 6 pages                              Full PDF
        |                                            |
  PyMuPDF -> regex parser                  pymupdf4llm Markdown
        |                                            |
  TenderRequirements                 header + recursive chunking
        |                                            |
  SQLite JSON specs                         ChromaDB + embeddings
                                                     |
                                                     v
Chat request -> services/chat.py -> query expansion -> BM25 + MMR
                                                     |
                                  grounded prompt -> Gemini -> response
```

### Request lifecycle

**Upload:** `app.py` sends `POST /api/v1/tenders/upload`. `tenders.py` saves the PDF to `temp_uploads/`, creates a `processing` record, and schedules `background_process_tender()`.

**Ingestion:** `services/ingestion.py` calls `process_tender_pdf()`, assigns a document-hash fallback ID when no bid ID is extracted, chunks the full Markdown document, stores it in ChromaDB, and marks the SQLite record `completed`. Failures are persisted as `failed: ...`; the temporary file and database session are cleaned up.

**Polling:** Streamlit calls `GET /api/v1/tenders/{tender_id}/specs` until processing completes. Lookup supports both the generated job ID and extracted bid ID.

**Chat:** Streamlit sends `POST /api/v1/chat/`. `services/chat.py` loads structured specs and Chroma documents, builds the RAG chain, invokes query expansion and hybrid retrieval, then returns `ChatResponse` with the answer and up to three retrieved source snippets.

## Tech Stack

| Area | Implementation |
|---|---|
| Interface | Streamlit `>=1.61.1` |
| API | FastAPI `>=0.141.1` |
| Persistence | SQLite, SQLAlchemy `>=2.0.51`, JSON tender specs |
| PDF processing | PyMuPDF and `pymupdf4llm >=1.27.2.3` |
| Chunking | LangChain Markdown and recursive text splitters |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` via `sentence-transformers` |
| Retrieval | ChromaDB, BM25, MMR, LangChain `EnsembleRetriever` |
| LLM | Gemini through `langchain-google-genai` |
| Orchestration | LangChain LCEL, prompt templates, output parsers |
| Validation | Pydantic v2 |
| Configuration | `python-dotenv` and provider configuration dictionaries |
| Tooling | uv, pytest, Python 3.12 |

See [pyproject.toml](pyproject.toml) for the complete dependency set and version constraints.

## Quick Start

```bash
git clone https://github.com/00-Aryan/tenderiq.git
cd tenderiq

uv sync

# Create .env and configure the Gemini API credentials.

# Terminal 1: start the FastAPI application with an ASGI server.
uv run uvicorn tender_iq.main:app --app-dir src --reload

# Terminal 2: start the Streamlit interface.
uv run streamlit run app.py
```

The UI expects the API at `http://127.0.0.1:8000`. The API exposes automatic documentation at `/docs` when running.

## API Surface

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/tenders/upload` | Accept a PDF and start background ingestion |
| `GET` | `/api/v1/tenders/{tender_id}/specs` | Read processing status and extracted specs |
| `POST` | `/api/v1/chat/` | Ask a question and receive an answer with citations |

## Current Scope and Tradeoffs

- **Vehicle domain:** extraction fields and prompts target LMV, logistics, rental, transport-support, and driver/vehicle-service tenders. Upload validation currently checks only the `.pdf` extension.
- **No conversation memory:** each backend query is independent; Streamlit stores prior messages for display only.
- **Regex-first extraction:** structured extraction covers a limited field set. The LLM extraction fallback is experimental and not wired into ingestion.
- **Citation depth:** citations are drawn from the retrieved source list, with the first three returned to the client.
- **No authentication or tenant isolation:** the current local architecture is a single-user development system.
- **No OCR fallback:** image-only scanned PDFs are not guaranteed to produce usable text.
- **No production job queue:** FastAPI `BackgroundTasks` is suitable for the current workflow but is not a durable distributed worker system.

## Testing

```bash
uv run pytest -q
```

The suite covers PDF loading, chunk metadata, RAG metadata formatting, FastAPI chat validation, route mapping, and citation-source mapping. It does not run live Gemini calls or cover a full upload-to-answer integration path with real Chroma data.

## Roadmap

- Conversation memory for multi-turn analysis
- Eligibility matching between `UserProfile` and `TenderRequirements`
- LLM fallback and validation for incomplete structured extraction
- OCR support for scanned PDFs
- Durable background workers, authentication, and multi-user vector isolation
- Broader integration tests and production observability

## Project Status

The core document-grounded Q&A path is implemented: Streamlit UI, FastAPI API, background ingestion, structured extraction, Chroma indexing, hybrid retrieval, and Gemini answer generation. Eligibility matching, conversation memory, structured logging, OCR, authentication, and deployment remain future work.

## Author

**Aryan Kumar**  
Final Year B.S. Data Science and Applications — IIT Madras

[GitHub](https://github.com/00-Aryan) · [LinkedIn](https://linkedin.com/in/aryan-kumar-1969b819b/)
