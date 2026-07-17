import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.models import NodeRow, Selection, SelectionItem
from app.schemas.schemas import SelectionCreateRequest, SelectionOut

router = APIRouter(prefix="/selections", tags=["selections"])


def _content_key(node_ids: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(node_ids)).encode("utf-8")).hexdigest()


@router.post("", response_model=SelectionOut)
def create_selection(req: SelectionCreateRequest, db: Session = Depends(get_db)):
    
    nodes = db.query(NodeRow).filter(NodeRow.id.in_(req.node_ids)).all()
    if len(nodes) != len(set(req.node_ids)):
        found = {n.id for n in nodes}
        missing = set(req.node_ids) - found
        raise HTTPException(400, f"unknown node_ids: {sorted(missing)}")
    if any(n.document_id != req.document_id for n in nodes):
        raise HTTPException(400, "all node_ids must belong to document_id")

    key = _content_key(req.node_ids)
    existing = (
        db.query(Selection)
        .filter(Selection.document_id == req.document_id, Selection.content_key == key)
        .first()
    )
    if existing:
        item_ids = [i.node_id for i in existing.items]
        return SelectionOut(
            id=existing.id, document_id=existing.document_id, name=existing.name,
            created_at=existing.created_at, node_ids=item_ids, reused_existing=True,
        )

    sel = Selection(document_id=req.document_id, name=req.name, content_key=key)
    db.add(sel)
    db.flush()
    for n in nodes:
        db.add(SelectionItem(selection_id=sel.id, node_id=n.id, version_id=n.version_id))
    db.commit()

    return SelectionOut(
        id=sel.id, document_id=sel.document_id, name=sel.name,
        created_at=sel.created_at, node_ids=[n.id for n in nodes], reused_existing=False,
    )


@router.get("/{selection_id}", response_model=SelectionOut)
def get_selection(selection_id: str, db: Session = Depends(get_db)):
    sel = db.query(Selection).filter(Selection.id == selection_id).first()
    if sel is None:
        raise HTTPException(404, "selection not found")
    return SelectionOut(
        id=sel.id, document_id=sel.document_id, name=sel.name,
        created_at=sel.created_at, node_ids=[i.node_id for i in sel.items],
    )
