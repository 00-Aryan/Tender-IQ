"""
API Endpoints for Tender operations.
Handles file uploads, async job tracking, and retrieving parsed specs.
"""
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from tender_iq.api.schemas.tender import TenderUpload, TenderSpecs
from tender_iq.db.session import get_db
from tender_iq.crud import tenders as crud_tender

# Import your background service
from tender_iq.services.ingestion import background_process_tender

router = APIRouter()
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/upload", response_model=TenderUpload, status_code=status.HTTP_202_ACCEPTED)
async def upload_tender(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files supported.")

    # 1. Generate a unique Job ID for this specific upload
    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"

    # 2. Save the file temporarily to disk so the background task can read it
    file_path = UPLOAD_DIR / f"{job_id}.pdf"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Create the placeholder record in SQLite so the frontend can poll it
    crud_tender.create_pending_tender(db=db, tracking_id=job_id)

    # 4. Fire the background worker! (FastAPI handles this in a separate thread)
    background_tasks.add_task(background_process_tender, file_path, job_id)

    # 5. Return instantly (usually takes < 0.05 seconds)
    return TenderUpload(
        filename=file.filename,
        status="processing",
        tender_id=job_id 
    )

@router.get("/{tender_id}/specs", response_model=TenderSpecs)
def specification_tender(tender_id: str, db: Session = Depends(get_db)):
    """The frontend will poll this endpoint using the job_id."""
    db_tender = crud_tender.get_tender_by_id(db, tender_id)
    if not db_tender:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    
    return TenderSpecs(
        tender_id=db_tender.id,         # This is the job_id
        status=db_tender.status,        # processing, completed, or failed
        specs=db_tender.specs           # Empty if processing, filled if completed
    )