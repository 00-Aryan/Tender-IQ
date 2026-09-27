"""
API Endpoints for Chat and RAG interactions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import your Pydantic schemas
from tender_iq.api.schemas.chat import ChatRequest, ChatResponse
# Import database session dependency
from tender_iq.db.session import get_db
# Import the chat service layer
from tender_iq.services.chat import process_chat_query

router = APIRouter()

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
        
    except ValueError as e:
        # Handle cases where the Tender ID or vectors don't exist
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        # Handle unexpected LLM or ChromaDB failures safely
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating the answer: {str(e)}"
        )