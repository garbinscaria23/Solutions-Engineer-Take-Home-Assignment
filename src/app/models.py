# src/app/models.py
from sqlalchemy import Column, String, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from src.app.db import Base

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)

    transactions = relationship("Transaction", back_populates="merchant")
    events = relationship("Event", back_populates="merchant")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String, nullable=False)
    has_discrepancy = Column(Boolean, default=False, nullable=False, index=True)
    discrepancy_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    merchant = relationship("Merchant", back_populates="transactions")
    events = relationship("Event", back_populates="transaction", cascade="all, delete-orphan", order_by="Event.timestamp")

    @property
    def merchant_name(self) -> str:
        return self.merchant.name if self.merchant else None

class Event(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    merchant = relationship("Merchant", back_populates="events")
    transaction = relationship("Transaction", back_populates="events")
