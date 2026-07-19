# src/app/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, asc, cast, Integer
import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from src.app import models, schemas
from src.app.config import settings

def get_event(db: Session, event_id: str) -> Optional[models.Event]:
    return db.query(models.Event).filter(models.Event.event_id == event_id).first()

def get_merchant(db: Session, merchant_id: str) -> Optional[models.Merchant]:
    return db.query(models.Merchant).filter(models.Merchant.id == merchant_id).first()

def create_merchant(db: Session, merchant_id: str, name: str) -> models.Merchant:
    db_merchant = models.Merchant(id=merchant_id, name=name)
    db.add(db_merchant)
    db.commit()
    db.refresh(db_merchant)
    return db_merchant

def get_transaction(db: Session, transaction_id: str) -> Optional[models.Transaction]:
    return db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

def reconcile_transaction_logic(
    transaction: models.Transaction,
    events: List[models.Event],
    threshold_hours: float = 6.0
) -> Tuple[bool, Optional[str]]:
    """
    Executes business rules to identify reconciliation discrepancies.
    Returns (has_discrepancy, discrepancy_reason)
    """
    if not events:
        return False, None

    # Sort events by timestamp to analyze sequential state changes
    sorted_events = sorted(events, key=lambda e: e.timestamp)
    event_types = [e.event_type for e in sorted_events]

    # Check 1: Details mismatch (amount, currency, merchant ID must match across all events)
    first_event = sorted_events[0]
    for e in sorted_events:
        if e.amount != first_event.amount:
            return True, f"Amount mismatch: initiated {first_event.amount}, but saw event with {e.amount}"
        if e.currency != first_event.currency:
            return True, f"Currency mismatch: initiated {first_event.currency}, but saw event with {e.currency}"
        if e.merchant_id != first_event.merchant_id:
            return True, f"Merchant mismatch: initiated by {first_event.merchant_id}, but saw event with {e.merchant_id}"

    # Check 2: Settlement recorded for a failed payment
    if "payment_failed" in event_types and "settled" in event_types:
        return True, "Settlement recorded for a failed payment"

    # Check 3: Duplicate event types (conflicting state events other than exact duplicate id which is handled by idempotency)
    type_counts = {}
    for etype in event_types:
        type_counts[etype] = type_counts.get(etype, 0) + 1
    for etype, count in type_counts.items():
        if count > 1:
            return True, f"Duplicate conflicting events of type '{etype}'"

    # Check 4: Out of order transitions in timestamps
    initiated_idx = next((i for i, e in enumerate(sorted_events) if e.event_type == "payment_initiated"), -1)
    processed_idx = next((i for i, e in enumerate(sorted_events) if e.event_type == "payment_processed"), -1)
    settled_idx = next((i for i, e in enumerate(sorted_events) if e.event_type == "settled"), -1)
    failed_idx = next((i for i, e in enumerate(sorted_events) if e.event_type == "payment_failed"), -1)

    if initiated_idx != -1:
        if processed_idx != -1 and processed_idx < initiated_idx:
            return True, "Out-of-order: payment_processed occurs before payment_initiated"
        if settled_idx != -1 and settled_idx < initiated_idx:
            return True, "Out-of-order: settled occurs before payment_initiated"
        if failed_idx != -1 and failed_idx < initiated_idx:
            return True, "Out-of-order: payment_failed occurs before payment_initiated"

    if processed_idx != -1 and settled_idx != -1 and settled_idx < processed_idx:
        return True, "Out-of-order: settled occurs before payment_processed"

    # Check 5: Payment marked processed but never settled
    # If the transaction is in 'payment_processed' state (with no 'settled' or 'payment_failed')
    # and more than threshold_hours have passed since the processed timestamp.
    if "payment_processed" in event_types and "settled" not in event_types and "payment_failed" not in event_types:
        processed_event = next(e for e in sorted_events if e.event_type == "payment_processed")
        now = datetime.datetime.now(datetime.timezone.utc)
        elapsed = (now - processed_event.timestamp).total_seconds() / 3600.0
        if elapsed > threshold_hours:
            return True, f"Payment marked processed but never settled (elapsed: {elapsed:.2f} hours)"

    return False, None

def ingest_single_event(db: Session, event_data: schemas.EventIngest) -> Tuple[models.Event, bool]:
    """
    Ingests a single payment event. Implements idempotency and transaction reconciliation.
    Returns (Event, is_duplicate).
    """
    # 1. Idempotency Check
    existing_event = get_event(db, event_data.event_id)
    if existing_event:
        return existing_event, True

    # 2. Check and Create Merchant if needed
    merchant = get_merchant(db, event_data.merchant_id)
    if not merchant:
        merchant = create_merchant(db, event_data.merchant_id, event_data.merchant_name)

    # 3. Check and Create Transaction if needed
    transaction = get_transaction(db, event_data.transaction_id)
    if not transaction:
        transaction = models.Transaction(
            id=event_data.transaction_id,
            merchant_id=event_data.merchant_id,
            amount=event_data.amount,
            currency=event_data.currency,
            status=event_data.event_type,
            created_at=event_data.timestamp,
            updated_at=event_data.timestamp
        )
        db.add(transaction)
        db.flush()

    # 4. Create and Save Event
    db_event = models.Event(
        event_id=event_data.event_id,
        transaction_id=event_data.transaction_id,
        event_type=event_data.event_type,
        merchant_id=event_data.merchant_id,
        amount=event_data.amount,
        currency=event_data.currency,
        timestamp=event_data.timestamp
    )
    db.add(db_event)
    db.flush()

    # 5. Update Transaction State & Reconcile
    # Fetch all events including the newly added one
    events = db.query(models.Event).filter(models.Event.transaction_id == transaction.id).all()
    
    # Update status to match the latest event by timestamp
    latest_event = max(events, key=lambda e: e.timestamp)
    transaction.status = latest_event.event_type
    transaction.updated_at = latest_event.timestamp

    # Re-verify discrepancies
    has_disc, disc_reason = reconcile_transaction_logic(
        transaction, events, settings.DISCREPANCY_THRESHOLD_HOURS
    )
    transaction.has_discrepancy = has_disc
    transaction.discrepancy_reason = disc_reason

    db.commit()
    db.refresh(db_event)
    return db_event, False

def get_transactions(
    db: Session,
    merchant_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> List[models.Transaction]:
    """
    Query transactions with filters, pagination, and sorting.
    """
    query = db.query(models.Transaction)

    if merchant_id:
        query = query.filter(models.Transaction.merchant_id == merchant_id)
    if status:
        query = query.filter(models.Transaction.status == status)
    if start_date:
        query = query.filter(models.Transaction.created_at >= start_date)
    if end_date:
        query = query.filter(models.Transaction.created_at <= end_date)

    # Sorting
    if sort_by not in ["created_at", "updated_at", "amount", "status"]:
        sort_by = "created_at"
        
    col = getattr(models.Transaction, sort_by)
    if sort_order.lower() == "asc":
        query = query.order_by(asc(col))
    else:
        query = query.order_by(desc(col))

    return query.offset(skip).limit(limit).all()

def get_reconciliation_summary(db: Session) -> dict:
    """
    Calculate reconciliation summaries grouped by merchant, date, and status.
    """
    # 1. By Merchant
    merchant_summary = db.query(
        models.Merchant.id.label("merchant_id"),
        models.Merchant.name.label("merchant_name"),
        func.count(models.Transaction.id).label("total_transactions"),
        func.sum(models.Transaction.amount).label("total_amount"),
        func.sum(cast(models.Transaction.has_discrepancy, Integer)).label("discrepancy_count")
    ).join(models.Transaction, models.Merchant.id == models.Transaction.merchant_id)\
     .group_by(models.Merchant.id, models.Merchant.name).all()

    by_merchant = [
        schemas.ReconciliationSummaryGroup(
            dimension="merchant",
            group_value=f"{row.merchant_name} ({row.merchant_id})",
            total_transactions=row.total_transactions,
            total_amount=row.total_amount or Decimal("0.0"),
            discrepancy_count=row.discrepancy_count or 0
        ) for row in merchant_summary
    ]

    # 2. By Date (Group by calendar date of created_at)
    date_summary = db.query(
        func.date(models.Transaction.created_at).label("tx_date"),
        func.count(models.Transaction.id).label("total_transactions"),
        func.sum(models.Transaction.amount).label("total_amount"),
        func.sum(cast(models.Transaction.has_discrepancy, Integer)).label("discrepancy_count")
    ).group_by(func.date(models.Transaction.created_at))\
     .order_by(func.date(models.Transaction.created_at).desc()).all()

    by_date = [
        schemas.ReconciliationSummaryGroup(
            dimension="date",
            group_value=str(row.tx_date),
            total_transactions=row.total_transactions,
            total_amount=row.total_amount or Decimal("0.0"),
            discrepancy_count=row.discrepancy_count or 0
        ) for row in date_summary
    ]

    # 3. By Status
    status_summary = db.query(
        models.Transaction.status.label("tx_status"),
        func.count(models.Transaction.id).label("total_transactions"),
        func.sum(models.Transaction.amount).label("total_amount"),
        func.sum(cast(models.Transaction.has_discrepancy, Integer)).label("discrepancy_count")
    ).group_by(models.Transaction.status).all()

    by_status = [
        schemas.ReconciliationSummaryGroup(
            dimension="status",
            group_value=row.tx_status,
            total_transactions=row.total_transactions,
            total_amount=row.total_amount or Decimal("0.0"),
            discrepancy_count=row.discrepancy_count or 0
        ) for row in status_summary
    ]

    return {
        "by_merchant": by_merchant,
        "by_date": by_date,
        "by_status": by_status
    }

def get_reconciliation_discrepancies(db: Session, skip: int = 0, limit: int = 100) -> List[models.Transaction]:
    """
    Get all transactions flagged with a discrepancy.
    """
    return db.query(models.Transaction)\
             .filter(models.Transaction.has_discrepancy == True)\
             .order_by(models.Transaction.updated_at.desc())\
             .offset(skip).limit(limit).all()

def bulk_ingest_events(db: Session, events_data: List[schemas.EventIngest]) -> Tuple[int, int]:
    """
    Highly optimized batch ingestion of events. Handles database lookups and processing in-memory
    to avoid N+1 queries. Commits in a single transaction.
    """
    if not events_data:
        return 0, 0

    # Deduplicate within the input list itself, keeping only the first occurrence of each event_id
    seen_event_ids = set()
    unique_events_data = []
    for e in events_data:
        if e.event_id not in seen_event_ids:
            seen_event_ids.add(e.event_id)
            unique_events_data.append(e)

    # 1. Filter out already ingested events (Idempotency)
    event_ids = [e.event_id for e in unique_events_data]
    existing_events = db.query(models.Event.event_id).filter(models.Event.event_id.in_(event_ids)).all()
    existing_event_ids = {r[0] for r in existing_events}

    new_events_data = [e for e in unique_events_data if e.event_id not in existing_event_ids]
    if not new_events_data:
        return 0, len(existing_event_ids)

    # 2. Pre-fetch merchants to minimize database queries
    merchant_ids = {e.merchant_id for e in new_events_data}
    existing_merchants = db.query(models.Merchant).filter(models.Merchant.id.in_(list(merchant_ids))).all()
    merchant_cache = {m.id: m for m in existing_merchants}

    # 3. Pre-fetch transactions to minimize queries
    tx_ids = {e.transaction_id for e in new_events_data}
    existing_txs = db.query(models.Transaction).filter(models.Transaction.id.in_(list(tx_ids))).all()
    tx_cache = {t.id: t for t in existing_txs}

    # 4. Handle merchants in bulk
    for event in new_events_data:
        if event.merchant_id not in merchant_cache:
            db_merchant = models.Merchant(id=event.merchant_id, name=event.merchant_name)
            db.add(db_merchant)
            merchant_cache[event.merchant_id] = db_merchant

    db.flush()

    # 5. Process transactions and events
    events_to_add = []
    for event in new_events_data:
        if event.transaction_id not in tx_cache:
            db_tx = models.Transaction(
                id=event.transaction_id,
                merchant_id=event.merchant_id,
                amount=event.amount,
                currency=event.currency,
                status=event.event_type,
                created_at=event.timestamp,
                updated_at=event.timestamp
            )
            db.add(db_tx)
            tx_cache[event.transaction_id] = db_tx

        db_event = models.Event(
            event_id=event.event_id,
            transaction_id=event.transaction_id,
            event_type=event.event_type,
            merchant_id=event.merchant_id,
            amount=event.amount,
            currency=event.currency,
            timestamp=event.timestamp
        )
        events_to_add.append(db_event)
        db.add(db_event)

    db.flush()

    # 6. Re-evaluate transaction states and discrepancies in bulk
    affected_tx_ids = list(tx_ids)
    all_tx_events = db.query(models.Event).filter(models.Event.transaction_id.in_(affected_tx_ids)).all()

    tx_events_map = {}
    for e in all_tx_events:
        tx_events_map.setdefault(e.transaction_id, []).append(e)

    for tx_id, tx in tx_cache.items():
        tx_events = tx_events_map.get(tx_id, [])
        if tx_events:
            # Determine latest event by timestamp
            latest_event = max(tx_events, key=lambda e: e.timestamp)
            tx.status = latest_event.event_type
            tx.updated_at = latest_event.timestamp

            # Evaluate reconciliation discrepancies
            has_disc, disc_reason = reconcile_transaction_logic(
                tx, tx_events, settings.DISCREPANCY_THRESHOLD_HOURS
            )
            tx.has_discrepancy = has_disc
            tx.discrepancy_reason = disc_reason

    db.commit()
    return len(new_events_data), len(existing_event_ids)

