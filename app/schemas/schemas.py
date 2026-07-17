from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NodeOut(BaseModel):
    id: str
    node_type: str
    heading_number: Optional[str] = None
    heading_text: Optional[str] = None
    level: int
    order_index: int
    parent_id: Optional[str] = None
    body_text: str = ""
    table_rows: Optional[list[list[str]]] = None
    page_number: Optional[int] = None
    source: str
    skipped_levels: bool
    needs_review: bool
    content_hash: str

    class Config:
        from_attributes = True


class NodeWithChildrenOut(NodeOut):
    children: list["NodeWithChildrenOut"] = []


class IngestResponse(BaseModel):
    document_id: str
    document_name: str
    version_id: str
    version_number: int
    node_count: int


class SelectionCreateRequest(BaseModel):
    document_id: str
    name: str
    node_ids: list[str] = Field(..., min_length=1)


class SelectionOut(BaseModel):
    id: str
    document_id: str
    name: str
    created_at: datetime
    node_ids: list[str]
    reused_existing: bool = False


class GenerateRequest(BaseModel):
    selection_id: str
    force_new: bool = False  # see decision log: resubmission policy


class TestCaseOut(BaseModel):
    title: str
    steps: str
    expected_result: str
    risk_level: str


class GenerationOut(BaseModel):
    id: str
    selection_id: str
    status: str
    attempts: int
    test_cases: Optional[list[TestCaseOut]] = None
    error: Optional[str] = None
    created_at: str
    reused_existing: bool = False


class NodeStalenessOut(BaseModel):
    node_id: str
    logical_id: str
    is_stale: bool
    current_node_id: Optional[str] = None
    diff_summary: Optional[str] = None


class GenerationStalenessOut(BaseModel):
    generation_id: str
    is_stale: bool
    nodes: list[NodeStalenessOut]
