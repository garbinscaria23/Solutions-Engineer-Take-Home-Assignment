# src/app/routes/transactions.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from src.app import schemas, crud, db

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("", response_model=List[schemas.TransactionResponse])
def list_transactions(
    merchant_id: Optional[str] = Query(None, description="Filter by Merchant ID"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. payment_initiated, settled)"),
    start_date: Optional[datetime] = Query(None, description="Filter transactions created on or after date"),
    end_date: Optional[datetime] = Query(None, description="Filter transactions created on or before date"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Limit for pagination"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, updated_at, amount, status)"),
    sort_order: str = Query("desc", description="Sort direction (asc, desc)"),
    session: Session = Depends(db.get_db)
):
    """
    List all transactions with advanced filtering, sorting, and pagination.
    """
    transactions = crud.get_transactions(
        session,
        merchant_id=merchant_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return transactions

@router.get("/{transaction_id}", response_model=schemas.TransactionResponse)
def get_transaction_details(transaction_id: str, session: Session = Depends(db.get_db)):
    """
    Fetch comprehensive details for a single transaction, including its state transitions/event history.
    """
    transaction = crud.get_transaction(session, transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' not found"
        )
    return transaction
