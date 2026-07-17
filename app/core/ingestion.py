
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import Document, DocumentVersion, LogicalNode, NodeRow
from app.parsing.pdf_parser import Node as ParsedNode, flatten, parse_pdf
from app.versioning.matcher import full_diff


def get_or_create_document(db: Session, document_name: str) -> Document:
    doc = db.query(Document).filter(Document.name == document_name).first()
    if doc:
        return doc
    doc = Document(name=document_name)
    db.add(doc)
    db.flush()
    return doc


def _latest_version(db: Session, document_id: str) -> DocumentVersion | None:
    return (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )


def _rebuild_in_memory_tree_for_version(db: Session, version: DocumentVersion) -> ParsedNode:
    
    rows = db.query(NodeRow).filter(NodeRow.version_id == version.id).all()
    by_id: dict[str, ParsedNode] = {}
    for r in rows:
        by_id[r.id] = ParsedNode(
            id=r.id, doc_id=r.document_id, version=version.version_number,
            node_type=r.node_type, heading_number=r.heading_number, heading_text=r.heading_text,
            level=r.level, order_index=r.order_index, parent_id=r.parent_id, body_text=r.body_text or "",
            table_rows=r.table_rows_json, page_number=r.page_number, source=r.source,
            skipped_levels=r.skipped_levels, needs_review=r.needs_review, content_hash=r.content_hash,
        )
    root = None
    for r in rows:
        node = by_id[r.id]
        if r.node_type == "document":
            root = node
            continue
        parent = by_id.get(r.parent_id)
        if parent is not None:
            parent.children.append(node)
    return root


def ingest_pdf(db: Session, pdf_path: str, document_name: str) -> DocumentVersion:
    doc = get_or_create_document(db, document_name)
    prev_version = _latest_version(db, doc.id)
    next_version_number = (prev_version.version_number + 1) if prev_version else 1

    parsed_root = parse_pdf(pdf_path, doc_id=doc.id, version=next_version_number)

    version = DocumentVersion(
        document_id=doc.id, version_number=next_version_number,
        source_filename=pdf_path,
    )
    db.add(version)
    db.flush()

    # logical_id assignment
    if prev_version is None:
        # First ingestion: every node gets a brand-new logical identity.
        logical_id_by_new_node_id: dict[str, str] = {}
        for n in flatten(parsed_root):
            ln = LogicalNode(document_id=doc.id, first_seen_version_id=version.id,
                              label=n.heading_text or n.node_type)
            db.add(ln)
            db.flush()
            logical_id_by_new_node_id[n.id] = ln.id
    else:
        prev_root = _rebuild_in_memory_tree_for_version(db, prev_version)
        old_id_to_logical = {
            r.id: r.logical_id for r in db.query(NodeRow).filter(NodeRow.version_id == prev_version.id)
        }
        diffs = full_diff(prev_root, parsed_root)

        logical_id_by_new_node_id = {}
        matched_new_ids = set()
        for pair in diffs:
            if pair.new_node is None:
                continue
            matched_new_ids.add(pair.new_node.id)
            if pair.old_node is not None:
                # Same logical identity as before.
                logical_id_by_new_node_id[pair.new_node.id] = old_id_to_logical.get(pair.old_node.id)
            else:
                ln = LogicalNode(document_id=doc.id, first_seen_version_id=version.id,
                                  label=pair.new_node.heading_text or pair.new_node.node_type)
                db.add(ln)
                db.flush()
                logical_id_by_new_node_id[pair.new_node.id] = ln.id

        # Anything not covered by the section-level+positional diff (e.g. the
        # document root, or node types the matcher doesn't specifically visit)
        # falls back to a fresh logical identity. This is a deliberate,
        # visible fallback rather than a silent None -- see APPROACH.md
        # decision log, "what input did you not handle".
        for n in flatten(parsed_root):
            if n.id not in logical_id_by_new_node_id:
                ln = LogicalNode(document_id=doc.id, first_seen_version_id=version.id,
                                  label=n.heading_text or n.node_type)
                db.add(ln)
                db.flush()
                logical_id_by_new_node_id[n.id] = ln.id

    # Persist NodeRows.
    for n in flatten(parsed_root):
        db.add(NodeRow(
            id=n.id, document_id=doc.id, version_id=version.id,
            logical_id=logical_id_by_new_node_id[n.id], parent_id=n.parent_id,
            node_type=n.node_type, heading_number=n.heading_number, heading_text=n.heading_text,
            level=n.level, order_index=n.order_index, body_text=n.body_text,
            table_rows_json=n.table_rows, page_number=n.page_number, source=n.source,
            skipped_levels=n.skipped_levels, needs_review=n.needs_review, content_hash=n.content_hash,
        ))
    db.commit()
    return version
