from __future__ import annotations

import difflib
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from app.parsing.pdf_parser import Node, flatten, normalize_text

FUZZY_TITLE_THRESHOLD = 0.75


@dataclass
class MatchPair:
    old_node: Optional[Node]
    new_node: Optional[Node]
    status: str          # "unchanged" | "changed" | "new" | "removed"
    match_method: str    # "number" | "fuzzy_title" | "positional" | "root"


def section_own_content_hash(node: Node) -> str:
    parts = [node.heading_text or ""]
    for c in node.children:
        if c.node_type == "section":
            continue
        if c.node_type == "table" and c.table_rows:
            parts.append("\n".join("|".join(row) for row in c.table_rows))
        else:
            parts.append(c.body_text or "")
    return hashlib.sha256(normalize_text("\n".join(parts)).encode("utf-8")).hexdigest()


def _sections_by_number(root: Node) -> dict[str, Node]:
    return {n.heading_number: n for n in flatten(root) if n.node_type == "section"}


def _fuzzy_pair_unmatched(old_unmatched: dict[str, Node], new_unmatched: dict[str, Node]):
    candidates = []
    for old_num, old_node in old_unmatched.items():
        for new_num, new_node in new_unmatched.items():
            score = difflib.SequenceMatcher(
                None, (old_node.heading_text or "").lower(), (new_node.heading_text or "").lower()
            ).ratio()
            if score >= FUZZY_TITLE_THRESHOLD:
                candidates.append((score, old_num, new_num))
    candidates.sort(reverse=True)  # best matches first
    used_old, used_new = set(), set()
    pairs = []
    for score, old_num, new_num in candidates:
        if old_num in used_old or new_num in used_new:
            continue
        pairs.append((old_num, new_num, score))
        used_old.add(old_num)
        used_new.add(new_num)
    return pairs


def match_sections(old_root: Node, new_root: Node) -> list[MatchPair]:
    old_secs = _sections_by_number(old_root)
    new_secs = _sections_by_number(new_root)

    matched_numbers = set(old_secs) & set(new_secs)
    old_unmatched = {k: v for k, v in old_secs.items() if k not in matched_numbers}
    new_unmatched = {k: v for k, v in new_secs.items() if k not in matched_numbers}

    results: list[MatchPair] = []

    for num in matched_numbers:
        old_n, new_n = old_secs[num], new_secs[num]
        status = "unchanged" if section_own_content_hash(old_n) == section_own_content_hash(new_n) else "changed"
        results.append(MatchPair(old_n, new_n, status, "number"))

    fuzzy_pairs = _fuzzy_pair_unmatched(old_unmatched, new_unmatched)
    for old_num, new_num, _score in fuzzy_pairs:
        old_n, new_n = old_unmatched.pop(old_num), new_unmatched.pop(new_num)
        status = "unchanged" if section_own_content_hash(old_n) == section_own_content_hash(new_n) else "changed"
        results.append(MatchPair(old_n, new_n, status, "fuzzy_title"))

    for node in old_unmatched.values():
        results.append(MatchPair(node, None, "removed", "number"))
    for node in new_unmatched.values():
        results.append(MatchPair(None, node, "new", "number"))

    return results


def match_children_positionally(old_section: Optional[Node], new_section: Optional[Node]) -> list[MatchPair]:
   
    def by_type(section):
        d = defaultdict(list)
        if section is not None:
            for c in section.children:
                if c.node_type != "section":
                    d[c.node_type].append(c)
        return d

    old_by_type = by_type(old_section)
    new_by_type = by_type(new_section)
    results = []
    for t in set(old_by_type) | set(new_by_type):
        olds, news = old_by_type.get(t, []), new_by_type.get(t, [])
        for i in range(max(len(olds), len(news))):
            o = olds[i] if i < len(olds) else None
            n = news[i] if i < len(news) else None
            if o is not None and n is not None:
                status = "unchanged" if o.content_hash == n.content_hash else "changed"
            elif n is not None:
                status = "new"
            else:
                status = "removed"
            results.append(MatchPair(o, n, status, "positional"))
    return results


def full_diff(old_root: Node, new_root: Node) -> list[MatchPair]:
    section_pairs = match_sections(old_root, new_root)
    out = list(section_pairs)
    for pair in section_pairs:
        out.extend(match_children_positionally(pair.old_node, pair.new_node))
    return out
