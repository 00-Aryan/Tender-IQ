"""
SQLAlchemy physical database schemas.

This module defines the actual tables and columns created in SQLite/PostgreSQL. 
These models are responsible for persistent storage and should never be 
returned directly to the client without passing through a Pydantic schema first.
"""
from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.sql import func
from tender_iq.db.session import Base

class TenderRecord(Base):
    __tablename__ = "tenders"

    id = Column(String, primary_key=True, index=True)
    bid_id = Column(String, index=True, nullable=True)  # Removed unique=True!
    status = Column(String, nullable=False, default="processing")
    specs = Column(JSON, nullable=False) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())