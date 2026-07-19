# src/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.app.db import engine, Base
from src.app.routes import events, transactions, reconciliation

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Setu Reconciliation Backend Service",
    description="Ingests payment lifecycle events, maintains transaction state, and flags settlement discrepancies.",
    version="1.0.0",
    lifespan=lifespan
)

# Register routers
app.include_router(events.router)
app.include_router(transactions.router)
app.include_router(reconciliation.router)

@app.get("/", tags=["General"])
def read_root():
    return {
        "status": "healthy",
        "service": "Setu Reconciliation API",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    from src.app.config import settings
    uvicorn.run("src.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
