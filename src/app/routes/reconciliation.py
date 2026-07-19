# src/app/routes/reconciliation.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from src.app import schemas, crud, db

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])

@router.get("/summary", response_model=schemas.ReconciliationSummaryResponse)
def get_reconciliation_summary(session: Session = Depends(db.get_db)):
    """
    Get aggregated reconciliation summaries grouped by merchant, date, and status.
    """
    summary = crud.get_reconciliation_summary(session)
    return summary

@router.get("/discrepancies", response_model=List[schemas.TransactionResponse])
def list_discrepancies(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Limit for pagination"),
    session: Session = Depends(db.get_db)
):
    """
    Get all transactions flagged with inconsistencies/discrepancies (e.g. out-of-order, failed but settled, processed but not settled).
    """
    discrepancies = crud.get_reconciliation_discrepancies(session, skip=skip, limit=limit)
    return discrepancies
