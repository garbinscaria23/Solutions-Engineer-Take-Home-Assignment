# src/app/routes/events.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from src.app import schemas, crud, db

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("", response_model=schemas.EventResponse, status_code=status.HTTP_201_CREATED)
def ingest_event(event: schemas.EventIngest, session: Session = Depends(db.get_db)):
    """
    Ingest a payment lifecycle event. Ingestion is idempotent based on event_id.
    """
    db_event, is_duplicate = crud.ingest_single_event(session, event)
    return db_event
