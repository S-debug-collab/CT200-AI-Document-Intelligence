"""
NoSQL store for generated test-case output.

The assignment allows "MongoDB local/Atlas free tier, or a well-justified
JSON store". We use a JSON-file store here because this environment has no
network access to stand up Mongo (local or Atlas) -- see APPROACH.md. The
interface below (insert / find_by_selection / find_by_node / get) is exactly
the shape a thin pymongo wrapper would have, so swapping the implementation
is a single-file change; nothing in app/api/ would need to change.

Each record:
{
  "id": str,
  "selection_id": str,
  "document_id": str,
  "status": "ok" | "failed",
  "prompt_model": str,
  "created_at": iso str,
  "attempts": int,
  "test_cases": [ {title, steps, expected_result, risk_level}, ... ] | None,
  "raw_responses": [str, ...],
  "error": str | None,
  "source_snapshot": [
      {"node_id": str, "logical_id": str, "version_id": str,
       "content_hash": str, "heading_text": str, "excerpt": str}
  ]
}
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

_LOCK = threading.Lock()
_DEFAULT_PATH = os.environ.get("GENERATIONS_STORE_PATH", "./data_store/generations.json")


class JsonGenerationStore:
    def __init__(self, path: str = _DEFAULT_PATH):
        self.path = path
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump([], f)

    def _read_all(self) -> list[dict]:
        with open(self.path, "r") as f:
            return json.load(f)

    def _write_all(self, records: list[dict]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(records, f, indent=2, default=str)
        os.replace(tmp, self.path)

    def insert(self, record: dict) -> dict:
        record = dict(record)
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        with _LOCK:
            records = self._read_all()
            records.append(record)
            self._write_all(records)
        return record

    def get(self, generation_id: str) -> Optional[dict]:
        for r in self._read_all():
            if r["id"] == generation_id:
                return r
        return None

    def find_by_selection(self, selection_id: str) -> list[dict]:
        return [r for r in self._read_all() if r["selection_id"] == selection_id]

    def find_by_node(self, node_id: str) -> list[dict]:
        """A node here means a specific pinned (node_id, version) that appeared in some selection's source_snapshot."""
        out = []
        for r in self._read_all():
            if any(s["node_id"] == node_id for s in r.get("source_snapshot", [])):
                out.append(r)
        return out

    def find_by_logical_id(self, logical_id: str) -> list[dict]:
        out = []
        for r in self._read_all():
            if any(s.get("logical_id") == logical_id for s in r.get("source_snapshot", [])):
                out.append(r)
        return out
