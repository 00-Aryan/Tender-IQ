from contextlib import asynccontextmanager
from fastapi import FastAPI
from tender_iq.db.session import engine, Base
from tender_iq.db import models 

# 3. Import your routers 
from tender_iq.api.v1.endpoints import tenders, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    print("Booting up: Creating SQLite database and tables...")
    Base.metadata.create_all(bind=engine)
    print("Database initialization complete.")
    
    yield  # The FastAPI server runs while yielding
    
    # --- SHUTDOWN LOGIC ---
    print("Shutting down TenderIQ...")

# 4. Pass the lifespan to your FastAPI app instance
app = FastAPI(
    title="TenderIQ API",
    description="RAG-based tender analysis tool",
    lifespan=lifespan
)

# 5. Register your endpoint routes
app.include_router(tenders.router, prefix="/api/v1/tenders", tags=["Tenders"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])