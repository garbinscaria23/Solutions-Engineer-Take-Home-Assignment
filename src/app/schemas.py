# src/app/schemas.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

class EventIngest(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of event: payment_initiated, payment_processed, payment_failed, settled")
    transaction_id: str = Field(..., description="Associated transaction ID")
    merchant_id: str = Field(..., description="Associated merchant ID")
    merchant_name: str = Field(..., description="Name of the merchant")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., max_length=3, description="Currency code (e.g. INR)")
    timestamp: datetime = Field(..., description="Event timestamp")

    model_config = ConfigDict(from_attributes=True)

class EventResponse(BaseModel):
    event_id: str
    event_type: str
    amount: Decimal
    currency: str
    timestamp: datetime
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MerchantInfo(BaseModel):
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    id: str
    merchant_id: str
    merchant_name: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    has_discrepancy: bool
    discrepancy_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    events: List[EventResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ReconciliationSummaryGroup(BaseModel):
    dimension: str
    group_value: str
    total_transactions: int
    total_amount: Decimal
    discrepancy_count: int

    model_config = ConfigDict(from_attributes=True)

class ReconciliationSummaryResponse(BaseModel):
    by_merchant: List[ReconciliationSummaryGroup]
    by_date: List[ReconciliationSummaryGroup]
    by_status: List[ReconciliationSummaryGroup]
