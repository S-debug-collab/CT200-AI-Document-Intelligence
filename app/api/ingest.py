import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ingestion import ingest_pdf
from app.models.models import NodeRow
from app.schemas.schemas import IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestResponse)
async def ingest_document(
    document_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "only .pdf files are supported")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        version = ingest_pdf(db, tmp_path, document_name)
    finally:
        os.unlink(tmp_path)

    node_count = db.query(NodeRow).filter(NodeRow.version_id == version.id).count()
    return IngestResponse(
        document_id=version.document_id, document_name=document_name,
        version_id=version.id, version_number=version.version_number,
        node_count=node_count,
    )
