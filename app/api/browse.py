from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.staleness import check_node_staleness
from app.models.models import Document, DocumentVersion, NodeRow
from app.schemas.schemas import NodeOut, NodeStalenessOut, NodeWithChildrenOut

router = APIRouter(tags=["browse"])


def _resolve_version(db: Session, document_id: str, version_number: Optional[int]) -> DocumentVersion:
    q = db.query(DocumentVersion).filter(DocumentVersion.document_id == document_id)
    if version_number is not None:
        v = q.filter(DocumentVersion.version_number == version_number).first()
    else:
        v = q.order_by(DocumentVersion.version_number.desc()).first()
    if v is None:
        raise HTTPException(404, "document or version not found")
    return v


def _node_to_out(n: NodeRow) -> NodeOut:
    return NodeOut(
        id=n.id, node_type=n.node_type, heading_number=n.heading_number, heading_text=n.heading_text,
        level=n.level, order_index=n.order_index, parent_id=n.parent_id, body_text=n.body_text or "",
        table_rows=n.table_rows_json, page_number=n.page_number, source=n.source,
        skipped_levels=n.skipped_levels, needs_review=n.needs_review, content_hash=n.content_hash,
    )


@router.get("/documents/{document_id}/sections", response_model=list[NodeOut])
def list_top_level_sections(
    document_id: str,
    version: Optional[int] = Query(None, description="version number; defaults to latest"),
    db: Session = Depends(get_db),
):
    v = _resolve_version(db, document_id, version)
    root = db.query(NodeRow).filter(NodeRow.version_id == v.id, NodeRow.node_type == "document").first()
    if root is None:
        raise HTTPException(404, "version has no root node")
    top = (
        db.query(NodeRow)
        .filter(NodeRow.version_id == v.id, NodeRow.parent_id == root.id, NodeRow.node_type == "section")
        .order_by(NodeRow.order_index)
        .all()
    )
    return [_node_to_out(n) for n in top]




@router.get("/nodes/{node_id}", response_model=NodeWithChildrenOut)
def get_node(node_id: str, db: Session = Depends(get_db)):
    n = db.query(NodeRow).filter(NodeRow.id == node_id).first()
    if n is None:
        raise HTTPException(404, "node not found")
    children = db.query(NodeRow).filter(NodeRow.parent_id == n.id).order_by(NodeRow.order_index).all()
    out = NodeWithChildrenOut(**_node_to_out(n).model_dump())
    out.children = [NodeWithChildrenOut(**_node_to_out(c).model_dump()) for c in children]
    return out


@router.get("/documents/{document_id}/search", response_model=list[NodeOut])
def search_nodes(
    document_id: str,
    q: str = Query(..., min_length=2),
    version: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    v = _resolve_version(db, document_id, version)
    like = f"%{q}%"
    rows = (
        db.query(NodeRow)
        .filter(
            NodeRow.version_id == v.id,
            or_(NodeRow.heading_text.ilike(like), NodeRow.body_text.ilike(like)),
        )
        .order_by(NodeRow.order_index)
        .all()
    )
    return [_node_to_out(n) for n in rows]


@router.get("/nodes/{node_id}/staleness", response_model=NodeStalenessOut)
def node_staleness(node_id: str, db: Session = Depends(get_db)):
    """Whether this specific pinned node has changed relative to the document's latest version."""
    n = db.query(NodeRow).filter(NodeRow.id == node_id).first()
    if n is None:
        raise HTTPException(404, "node not found")
    result = check_node_staleness(db, n.document_id, node_id)
    return NodeStalenessOut(
        node_id=result.node_id, logical_id=result.logical_id, is_stale=result.is_stale,
        current_node_id=result.current_node_id, diff_summary=result.diff_summary,
    )
