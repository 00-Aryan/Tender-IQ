"""
CRUD operations and database interactions for Tender records.

This module isolates all SQL/database logic (Create, Read, Update, Delete) 
from the FastAPI endpoints. It accepts database sessions and primitive data 
(or Pydantic models) and returns SQLAlchemy ORM instances to be serialized 
by the API layer.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session
from tender_iq.db.models import TenderRecord


def create_pending_tender(db: Session, tracking_id: str) -> TenderRecord:
    """Creates the initial placeholder record when the PDF is uploaded."""
    db_tender = TenderRecord(
        id=tracking_id,
        status="processing",
        specs={}  # Empty initially
    )
    db.add(db_tender)
    db.commit()
    return db_tender

def update_parsed_tender(db: Session, tracking_id: str, real_bid_id: str, specs_dict: dict):
    """Overwrites the pending record with the Regex extracted data."""
    db_tender = db.query(TenderRecord).filter(TenderRecord.id == tracking_id).first()
    if db_tender:
        # DO NOT change db_tender.id! Keep it as tracking_id so polling works.
        db_tender.bid_id = real_bid_id  
        db_tender.specs = specs_dict
        db_tender.status = "completed"
        db.commit()

def mark_tender_failed(db: Session, tracking_id: str):
    """Marks the tender as failed if PyMuPDF or Regex crashes."""
    db_tender = db.query(TenderRecord).filter(TenderRecord.id == tracking_id).first()
    if db_tender:
        db_tender.status = "failed"
        db.commit()

def get_tender_by_id(db: Session, tender_id: str) -> TenderRecord | None:
    """
    Retrieve a single tender record by either its internal record id or GeM bid_id.

    Args:
        db (Session): The active database session injected by FastAPI.
        tender_id (str): Either the database primary-key id or the tender bid_id.

    Returns:
        TenderRecord | None: The matching ORM record, or None if not found.
    """
    return db.query(TenderRecord).filter(
        or_(TenderRecord.id == tender_id, TenderRecord.bid_id == tender_id)
    ).first()
