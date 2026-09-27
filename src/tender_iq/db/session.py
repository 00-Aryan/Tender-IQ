"""
Database session management and connection pooling.

This module initializes the SQLAlchemy engine and provides the Dependency 
Injection generator (`get_db`) used by FastAPI endpoints to safely open 
and close database transactions per request.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./tenderiq_dev.db"

# connect_args is needed only for SQLite to prevent thread errors in FastAPI , it talks to the database
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

#staging area means reading or writing happens inside session, session maker does not open session immediately it creates a configuration so every time i call sessionLocal(), it generated a new session, bind tells to route all queries through engine created above 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# It manages the connection pool and acts as a translator, converting SQLAlchemy's Python commands into raw SQL syntax