
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)

    versions = relationship("DocumentVersion", back_populates="document",
                             order_by="DocumentVersion.version_number")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    source_filename = Column(String)
    ingested_at = Column(DateTime, default=_now)

    document = relationship("Document", back_populates="versions")
    nodes = relationship("NodeRow", back_populates="version")

    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_doc_version"),)


class LogicalNode(Base):
    __tablename__ = "logical_nodes"
    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    first_seen_version_id = Column(String, ForeignKey("document_versions.id"))
    # Best-effort human label for admin/debug views -- NOT used for matching.
    label = Column(String, nullable=True)


class NodeRow(Base):
    __tablename__ = "nodes"
    # Reuse the parser-generated id (unique per document+version) as PK.
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    version_id = Column(String, ForeignKey("document_versions.id"), nullable=False)
    logical_id = Column(String, ForeignKey("logical_nodes.id"), nullable=False)
    parent_id = Column(String, ForeignKey("nodes.id"), nullable=True)

    node_type = Column(String, nullable=False)       # document|section|paragraph|list_item|table
    heading_number = Column(String, nullable=True)
    heading_text = Column(String, nullable=True)
    level = Column(Integer, nullable=False, default=0)
    order_index = Column(Integer, nullable=False, default=0)
    body_text = Column(Text, default="")
    table_rows_json = Column(JSON, nullable=True)
    page_number = Column(Integer, nullable=True)
    source = Column(String, default="text")          # text|ocr
    skipped_levels = Column(Boolean, default=False)
    needs_review = Column(Boolean, default=False)
    content_hash = Column(String, nullable=False)

    version = relationship("DocumentVersion", back_populates="nodes")


class Selection(Base):
    __tablename__ = "selections"
    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    name = Column(String, nullable=False)
    # sha256 of the sorted set of pinned node ids -- our idempotency key.
    # See app/api/selections.py for the resubmission policy this enables.
    content_key = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=_now)

    items = relationship("SelectionItem", back_populates="selection")


class SelectionItem(Base):
    __tablename__ = "selection_items"
    id = Column(String, primary_key=True, default=_uuid)
    selection_id = Column(String, ForeignKey("selections.id"), nullable=False)
    node_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    version_id = Column(String, ForeignKey("document_versions.id"), nullable=False)

    selection = relationship("Selection", back_populates="items")
