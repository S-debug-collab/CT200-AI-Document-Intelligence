from fastapi import FastAPI

from app.api import browse, generation, ingest, retrieval, selections
from app.core.db import init_db

app = FastAPI(
    title="Tri9T CT-200 Document Intelligence API",
    description="Ingest the CT-200 manual, browse its hierarchy, version it, "
                "select sections, and generate QA test-case ideas with staleness tracking.",
    version="0.1.0",
)

@app.on_event("startup")
def _startup():
    init_db()

app.include_router(ingest.router)
app.include_router(browse.router)
app.include_router(selections.router)
app.include_router(generation.router)
app.include_router(retrieval.router)

@app.get("/health")
def health():
    return {"status": "ok"}