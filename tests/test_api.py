# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime
from decimal import Decimal

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.app.main import app
from src.app.db import Base, get_db
from src.app import models

# Use a test PostgreSQL database or the default local one since it's portable.
# We will use the default local one, but clear tables before starting the tests.
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # Setup test tables
    engine = create_engine("postgresql://postgres@localhost:5432/setu_reconciliation")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup after tests
    # Base.metadata.drop_all(bind=Base.metadata.bind or create_engine("postgresql://postgres@localhost:5432/setu_reconciliation"))

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_event_ingestion_and_idempotency():
    # 1. Ingest payment_initiated event
    event_payload = {
        "event_id": "test-event-1",
        "event_type": "payment_initiated",
        "transaction_id": "test-tx-1",
        "merchant_id": "test-merchant",
        "merchant_name": "Test Merchant Store",
        "amount": 500.50,
        "currency": "INR",
        "timestamp": "2026-07-19T10:00:00+00:00"
    }
    response = client.post("/events", json=event_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["event_id"] == "test-event-1"
    assert data["event_type"] == "payment_initiated"

    # 2. Ingest duplicate event (idempotency check)
    response_dup = client.post("/events", json=event_payload)
    assert response_dup.status_code == 201  # Should succeed idempotently
    assert response_dup.json()["event_id"] == "test-event-1"

    # 3. Retrieve transaction and check status
    response_tx = client.get("/transactions/test-tx-1")
    assert response_tx.status_code == 200
    tx_data = response_tx.json()
    assert tx_data["id"] == "test-tx-1"
    assert tx_data["status"] == "payment_initiated"
    assert float(tx_data["amount"]) == 500.50
    assert len(tx_data["events"]) == 1

def test_state_transitions_and_discrepancy_failed_settled():
    # Ingesting: initiated -> payment_failed -> settled (Discrepancy: Settled a failed payment)
    client.post("/events", json={
        "event_id": "tx2-event-init",
        "event_type": "payment_initiated",
        "transaction_id": "test-tx-2",
        "merchant_id": "test-merchant",
        "merchant_name": "Test Merchant Store",
        "amount": 1000.00,
        "currency": "INR",
        "timestamp": "2026-07-19T10:00:00+00:00"
    })
    client.post("/events", json={
        "event_id": "tx2-event-fail",
        "event_type": "payment_failed",
        "transaction_id": "test-tx-2",
        "merchant_id": "test-merchant",
        "merchant_name": "Test Merchant Store",
        "amount": 1000.00,
        "currency": "INR",
        "timestamp": "2026-07-19T10:05:00+00:00"
    })
    client.post("/events", json={
        "event_id": "tx2-event-settle",
        "event_type": "settled",
        "transaction_id": "test-tx-2",
        "merchant_id": "test-merchant",
        "merchant_name": "Test Merchant Store",
        "amount": 1000.00,
        "currency": "INR",
        "timestamp": "2026-07-19T10:10:00+00:00"
    })

    # Fetch transaction
    response_tx = client.get("/transactions/test-tx-2")
    tx_data = response_tx.json()
    assert tx_data["status"] == "settled"
    assert tx_data["has_discrepancy"] is True
    assert "Settlement recorded for a failed payment" in tx_data["discrepancy_reason"]

def test_details_mismatch_discrepancy():
    # Ingest events for same transaction ID but differing amounts
    client.post("/events", json={
        "event_id": "tx3-event-init",
        "event_type": "payment_initiated",
        "transaction_id": "test-tx-3",
        "merchant_id": "test-merchant",
        "merchant_name": "Test Merchant Store",
        "amount": 100.00,
        "currency": "INR",
        "timestamp": "2026-07-19T10:00:00+00:00"
    })
    client.post("/events", json={
        "event_id": "tx3-event-proc",
        "event_type": "payment_processed",
        "transaction_id": "test-tx-3",
        "merchant_id": "test-merchant",
        "merchant_name": "Test Merchant Store",
        "amount": 150.00,  # CONFLECTING AMOUNT!
        "currency": "INR",
        "timestamp": "2026-07-19T10:05:00+00:00"
    })

    # Fetch transaction
    response_tx = client.get("/transactions/test-tx-3")
    tx_data = response_tx.json()
    assert tx_data["has_discrepancy"] is True
    assert "Amount mismatch" in tx_data["discrepancy_reason"]

def test_reconciliation_summary():
    response = client.get("/reconciliation/summary")
    assert response.status_code == 200
    summary = response.json()
    
    # Check dimensions exist
    assert "by_merchant" in summary
    assert "by_date" in summary
    assert "by_status" in summary

    # Check merchant stats
    merchants = [m["group_value"] for m in summary["by_merchant"]]
    assert any("Test Merchant Store" in name for name in merchants)

def test_reconciliation_discrepancies_list():
    response = client.get("/reconciliation/discrepancies")
    assert response.status_code == 200
    disc_list = response.json()
    # test-tx-2 and test-tx-3 should have discrepancies
    tx_ids = [tx["id"] for tx in disc_list]
    assert "test-tx-2" in tx_ids
    assert "test-tx-3" in tx_ids
