"""
API Endpoints for Chat and RAG interactions.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import your Pydantic schemas
from tender_iq.api.schemas.chat import ChatRequest, ChatResponse
# Import database session dependency
from tender_iq.db.session import get_db
# Import the chat service layer
from tender_iq.services.chat import (
    TenderDocumentsNotFoundError,
    TenderNotFoundError,
    process_chat_query,
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def chat_with_tender(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Accepts a user query and a tender_id, runs the RAG pipeline, 
    and returns the LLM response with document citations.
    """
    try:
        # Pass the validated request data to the service layer
        response_data = process_chat_query(
            db=db, 
            tender_id=request.tender_id, 
            query=request.query
        )
        return response_data
        
    except TenderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested tender not found."
        ) from None
    except TenderDocumentsNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested tender documents are not available."
        ) from None
    except Exception:
        logger.exception(
            "Unexpected error while processing chat request for tender_id=%s",
            request.tender_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing your request. Please try again."
        ) from None