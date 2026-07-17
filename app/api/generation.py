import os

from dotenv import load_dotenv

load_dotenv()
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.llm.client import LLMClient, MockLLMClient, RealLLMClient, generate_test_cases
from app.models.models import NodeRow, Selection, SelectionItem
from app.schemas.schemas import GenerateRequest, GenerationOut, TestCaseOut
from app.store.json_store import JsonGenerationStore
router = APIRouter(prefix="/generate", tags=["generation"])

_store = JsonGenerationStore()


def _get_llm_client() -> LLMClient:
    if os.environ.get("LLM_API_KEY"):
        print("Using Real LLM")
        return RealLLMClient()

    print("Using Mock LLM")
    return MockLLMClient()

def _collect_descendants(db: Session, node: NodeRow):
    nodes = [node]

    children = (
        db.query(NodeRow)
        .filter(NodeRow.parent_id == node.id)
        .order_by(NodeRow.order_index)
        .all()
    )

    for child in children:
        nodes.extend(_collect_descendants(db, child))

    return nodes


def _reconstruct_text(nodes: list[NodeRow]) -> str:
    parts = []
    for n in sorted(nodes, key=lambda n: n.order_index):
        if n.node_type == "table" and n.table_rows_json:
            parts.append("\n".join(" | ".join(row) for row in n.table_rows_json))
        elif n.heading_text:
            parts.append(f"{n.heading_number or ''} {n.heading_text}".strip())
            if n.body_text:
                parts.append(n.body_text)
        else:
            parts.append(n.body_text or "")
    return "\n\n".join(p for p in parts if p)


@router.post("", response_model=GenerationOut)
def generate(req: GenerateRequest, db: Session = Depends(get_db)):
    sel = db.query(Selection).filter(Selection.id == req.selection_id).first()
    if sel is None:
        raise HTTPException(404, "selection not found")

    if not req.force_new:
        existing = [r for r in _store.find_by_selection(sel.id) if r["status"] == "ok"]
        if existing:
            latest = max(existing, key=lambda r: r["created_at"])
            return GenerationOut(
                id=latest["id"], selection_id=sel.id, status=latest["status"],
                attempts=latest["attempts"],
                test_cases=[TestCaseOut(**tc) for tc in (latest["test_cases"] or [])],
                error=latest.get("error"), created_at=latest["created_at"], reused_existing=True,
            )

    items = db.query(SelectionItem).filter(
    SelectionItem.selection_id == sel.id).all()

    nodes = []

    for item in items:
        root = db.query(NodeRow).filter(
            NodeRow.id == item.node_id).first()

        if root is None:
            continue

    # Include the selected node itself
        nodes.append(root)

        # Recursively collect all descendants
        queue = [root.id]

        while queue:
            parent_id = queue.pop(0)

            children = (
                db.query(NodeRow)
                .filter(NodeRow.parent_id == parent_id)
                .order_by(NodeRow.order_index)
                .all()
            )

            for child in children:
                nodes.append(child)
                queue.append(child.id)

# Remove duplicates while preserving order
    seen = set()
    unique_nodes = []

    for node in sorted(nodes, key=lambda n: n.order_index):
        if node.id not in seen:
            seen.add(node.id)
            unique_nodes.append(node)

    nodes = unique_nodes

    if not nodes:
        raise HTTPException(400, "selection has no resolvable nodes")

    text = _reconstruct_text(nodes)
    client = _get_llm_client()
    outcome = generate_test_cases(client, text)

    source_snapshot = [
        {
            "node_id": n.id, "logical_id": n.logical_id, "version_id": n.version_id,
            "content_hash": n.content_hash, "heading_text": n.heading_text,
            "excerpt": (n.body_text or "")[:200],
        }
        for n in nodes
    ]

    record = _store.insert({
        "selection_id": sel.id,
        "document_id": sel.document_id,
        "status": outcome.status,
        "prompt_model": getattr(client, "model", "mock"),
        "attempts": outcome.attempts,
        "test_cases": outcome.test_cases,
        "raw_responses": outcome.raw_responses,
        "error": outcome.error,
        "source_snapshot": source_snapshot,
    })

    return GenerationOut(
        id=record["id"], selection_id=sel.id, status=record["status"], attempts=record["attempts"],
        test_cases=[TestCaseOut(**tc) for tc in (record["test_cases"] or [])] if record["test_cases"] else None,
        error=record["error"], created_at=record["created_at"], reused_existing=False,
    )
