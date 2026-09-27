"""
Background service for asynchronous PDF ingestion.
"""
import hashlib
import os
from pathlib import Path

from tender_iq.db.session import SessionLocal
from tender_iq.crud import tenders as crud_tender

# Your existing logic
from tender_iq.extraction.extract_data import process_tender_pdf
from tender_iq.document_processor.loader import load_tender_pdf
from tender_iq.document_processor.chunker import chunk_tender_documents
from tender_iq.vector_store.chroma_store import store_tender

def background_process_tender(file_path: Path, job_id: str):
    """
    Background worker that extracts data and syncs both ChromaDB and SQLite.
    """
    # 1. Open a dedicated database session for this thread
    db = SessionLocal()
    
    try:
        tmp_path = str(file_path)

        # 2. Run your Regex Extraction (Max 6 pages, ~5 seconds)
        tender_obj = process_tender_pdf(tmp_path)
        real_bid_id = tender_obj.bid_id

        # 3. Defensive check: Fall back to content hash if Bid ID is missing
        if not real_bid_id:
            with open(tmp_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()[:12]
            real_bid_id = f"DOC_{file_hash}"
            # Ensure the Pydantic object also holds this fallback ID
            tender_obj.bid_id = real_bid_id

        # 4. Text Extraction and Chunking (For ChromaDB)
        markdown_text = load_tender_pdf(tmp_path)
        chunks = chunk_tender_documents(markdown_text)

        # 5. Store in ChromaDB using the REAL GeM ID
        store_tender(chunks, real_bid_id)

        # 6. Update SQLite: Mark job as completed and inject the real ID/Specs
        specs_dict = tender_obj.model_dump(mode="json")
        
        # We pass the real_bid_id into the dictionary so the frontend can retrieve it
        specs_dict["bid_id"] = real_bid_id 
        
        crud_tender.update_parsed_tender(
            db=db,
            tracking_id=job_id,
            real_bid_id=real_bid_id,
            specs_dict=specs_dict
        )

    except Exception as e:
        # 7. If PyMuPDF or Regex crashes, tell SQLite so the frontend stops polling
        print(f"Background Job {job_id} failed: {e}")
        crud_tender.mark_tender_failed(db, job_id, str(e))
        
    finally:
        # 8. Cleanup: Delete the PDF and close the DB connection
        if file_path.exists():
            os.unlink(tmp_path)
        db.close()