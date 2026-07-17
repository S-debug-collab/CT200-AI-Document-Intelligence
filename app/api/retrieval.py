from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.staleness import check_generation_staleness
from app.schemas.schemas import GenerationOut, GenerationStalenessOut, NodeStalenessOut, TestCaseOut
from app.store.json_store import JsonGenerationStore

router = APIRouter(prefix="/retrieve", tags=["retrieval"])
_store = JsonGenerationStore()


def _record_to_out(r: dict) -> GenerationOut:
    return GenerationOut(
        id=r["id"], selection_id=r["selection_id"], status=r["status"], attempts=r["attempts"],
        test_cases=[TestCaseOut(**tc) for tc in (r["test_cases"] or [])] if r["test_cases"] else None,
        error=r.get("error"), created_at=r["created_at"],
    )


@router.get("/by-selection/{selection_id}", response_model=list[GenerationOut])
def get_by_selection(selection_id: str):
    return [_record_to_out(r) for r in _store.find_by_selection(selection_id)]


@router.get("/by-node/{node_id}", response_model=list[GenerationOut])
def get_by_node(node_id: str):
    
    return [_record_to_out(r) for r in _store.find_by_node(node_id)]


@router.get("/by-logical/{logical_id}", response_model=list[GenerationOut])
def get_by_logical(logical_id: str):
    return [_record_to_out(r) for r in _store.find_by_logical_id(logical_id)]


@router.get("/{generation_id}/staleness", response_model=GenerationStalenessOut)
def get_generation_staleness(generation_id: str, db: Session = Depends(get_db)):
    record = _store.get(generation_id)
    if record is None:
        raise HTTPException(404, "generation not found")
    result = check_generation_staleness(db, record["document_id"], record["source_snapshot"])
    return GenerationStalenessOut(
        generation_id=generation_id, is_stale=result["is_stale"],
        nodes=[NodeStalenessOut(**n) for n in result["nodes"]],
    )
