# Solutions-Engineer-Take-Home-Assignment

A production-grade transaction reconciliation engine built with **FastAPI** and **PostgreSQL**. The service ingests payment events, reconstructs transaction lifecycles, and flags discrepancies (e.g., amount/currency mismatches, settlement of failed payments, out-of-order events, duplicate records, and processing timeouts) based on structured business rules.

---

## 🚀 Live Public Deployment
The application is fully hosted on AWS:
*   **Base URL (Health Check)**: [http://43.205.94.73:8000/](http://43.205.94.73:8000/)
*   **Swagger API Documentation**: [http://43.205.94.73:8000/docs](http://43.205.94.73:8000/docs)
*   **AWS Relational Database**: Lightsail PostgreSQL (`postgres_16`) - Fully populated with all 10,165 events.

---

## 🏗️ Architecture & Stack
*   **Core Framework**: FastAPI (Asynchronous python web framework)
*   **Database**: PostgreSQL 16 (Relational DB for strong ACID constraints)
*   **ORM**: SQLAlchemy with Pydantic for validation and serialization
*   **Testing**: Pytest (automated integration tests suite)
*   **Containerization**: Docker (multi-stage builds)
*   **Infrastructure**: AWS Lightsail (Virtual Machine & Database instances)

---

## ⚙️ Features & Reconciliation Logic
The ingestion engine processes payment events (`payment_initiated`, `payment_processed`, `payment_failed`, `settled`) and detects the following anomalies:
1.  **Detail Mismatch**: Discrepancies in `amount`, `currency`, or `merchant_id` across events of a single transaction.
2.  **Settlement on Failure**: A transaction entering the `settled` state after a `payment_failed` event.
3.  **Out-of-Order Events**: Ingestion of events that occur chronologically before current transaction state.
4.  **Duplicate Events**: Safe idempotent handlers ignoring identical `event_id` records.
5.  **Processing Timeout**: Transactions remaining in `payment_processed` for >6 hours without a corresponding `settled` or `payment_failed` event.

---

## 🛠️ Local Installation & Run Guide

### 1. Prerequisites
Ensure you have **Python 3.10+** installed.

### 2. Extract and Initialize PostgreSQL
We supply a portable database script to start PostgreSQL locally in user-space without UAC prompts:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_postgres.ps1
```

### 3. Setup Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure Environment
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/setu_reconciliation
PORT=8000
HOST=127.0.0.1
DISCREPANCY_THRESHOLD_HOURS=6.0
```

### 5. Seed the Data
Populate the database with the ~10,000 events:
```powershell
python scripts/seed.py
```

### 6. Run the FastAPI Server
```powershell
uvicorn src.app.main:app --reload
```
Access the local API documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## 🧪 Running Tests
Execute the integration test suite using pytest:
```powershell
pytest
```

---

## 🐳 Docker Deployment
To build and run the container locally:
```bash
docker-compose up --build
```
