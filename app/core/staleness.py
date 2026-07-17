
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import DocumentVersion, NodeRow


@dataclass
class NodeStaleness:
    node_id: str
    logical_id: str
    is_stale: bool
    current_node_id: Optional[str]     # None if the logical node was removed entirely
    diff_summary: Optional[str]        # unified-diff-style text, only when stale and current_node_id is not None


def _latest_version_id(db: Session, document_id: str) -> Optional[str]:
    v = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    return v.id if v else None


def check_node_staleness(db: Session, document_id: str, node_id: str) -> NodeStaleness:
    pinned = db.query(NodeRow).filter(NodeRow.id == node_id).first()
    if pinned is None:
        raise ValueError(f"unknown node_id {node_id}")

    latest_vid = _latest_version_id(db, document_id)
    if latest_vid == pinned.version_id:
        return NodeStaleness(node_id, pinned.logical_id, False, node_id, None)

    current = (
        db.query(NodeRow)
        .filter(NodeRow.logical_id == pinned.logical_id, NodeRow.version_id == latest_vid)
        .first()
    )
    if current is None:
        # The section/paragraph this generation was based on no longer exists in the latest version.
        return NodeStaleness(node_id, pinned.logical_id, True, None,
                              "This content was removed in a later document version.")

    if current.content_hash == pinned.content_hash:
        return NodeStaleness(node_id, pinned.logical_id, False, current.id, None)

    diff = "\n".join(difflib.unified_diff(
        (pinned.body_text or pinned.heading_text or "").splitlines(),
        (current.body_text or current.heading_text or "").splitlines(),
        fromfile=f"v{db.query(DocumentVersion).get(pinned.version_id).version_number}",
        tofile=f"v{db.query(DocumentVersion).get(latest_vid).version_number}",
        lineterm="",
    ))
    return NodeStaleness(node_id, pinned.logical_id, True, current.id, diff or "(content changed)")


def check_generation_staleness(db: Session, document_id: str, source_snapshot: list[dict]) -> dict:
    
    results = []
    any_stale = False
    for item in source_snapshot:
        ns = check_node_staleness(db, document_id, item["node_id"])
        any_stale = any_stale or ns.is_stale
        results.append({
            "node_id": ns.node_id, "logical_id": ns.logical_id, "is_stale": ns.is_stale,
            "current_node_id": ns.current_node_id, "diff_summary": ns.diff_summary,
        })
    return {"is_stale": any_stale, "nodes": results}
