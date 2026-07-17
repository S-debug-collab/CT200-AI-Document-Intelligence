from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Optional

import pdfplumber

# Optional OCR fallback deps -- imported lazily so environments without
# poppler/tesseract installed can still run the text-layer-only path.
try:
    from pdf2image import convert_from_path
    import pytesseract
    _OCR_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    _OCR_AVAILABLE = False


HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,4})\.?\s+(.+)$")
BODY_FONT_SIZE_DEFAULT = 10.0
HEADING_SIZE_THRESHOLD = 1.4  # points larger than body => heading candidate


@dataclass
class Node:
    id: str
    doc_id: str
    version: int
    node_type: str  # "document" | "section" | "paragraph" | "list_item" | "table"
    heading_number: Optional[str]
    heading_text: Optional[str]
    level: int  # 0 = document root, 1..N = section depth
    order_index: int
    parent_id: Optional[str]
    body_text: str
    table_rows: Optional[list] = None
    page_number: Optional[int] = None
    source: str = "text"  # "text" | "ocr"
    skipped_levels: bool = False
    needs_review: bool = False
    content_hash: str = ""
    children: list = field(default_factory=list)  # populated only in the in-memory tree view

    def compute_hash(self) -> str:
        norm = normalize_text((self.heading_text or "") + "\n" + (self.body_text or ""))
        if self.table_rows:
            norm += "\n" + normalize_text(
                "\n".join("|".join(str(c) for c in row) for row in self.table_rows)
            )
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def to_dict(self, include_children=True):
        d = asdict(self)
        if not include_children:
            d.pop("children", None)
        return d


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash -> hyphen
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def _line_font_info(line_chars):
    if not line_chars:
        return BODY_FONT_SIZE_DEFAULT, False
    sizes = [c["size"] for c in line_chars]
    sizes.sort()
    size = sizes[len(sizes) // 2]
    bold_count = sum(1 for c in line_chars if "Bold" in (c.get("fontname") or ""))
    is_bold = bold_count >= len(line_chars) * 0.6
    return round(size, 1), is_bold


def _group_chars_into_lines(chars, y_tolerance=2.5):
    lines = []
    current = []
    current_top = None
    for c in sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"])):
        if current_top is None or abs(c["top"] - current_top) <= y_tolerance:
            current.append(c)
            current_top = c["top"] if current_top is None else current_top
        else:
            lines.append(current)
            current = [c]
            current_top = c["top"]
    if current:
        lines.append(current)
    return lines


def _estimate_body_font_size(all_lines):
    from collections import Counter
    sizes = Counter()
    for line_chars in all_lines:
        size, _ = _line_font_info(line_chars)
        text = "".join(c["text"] for c in line_chars).strip()
        if text:
            sizes[size] += len(text)
    if not sizes:
        return BODY_FONT_SIZE_DEFAULT
    return sizes.most_common(1)[0][0]


def _ocr_page_text(pdf_path: str, page_number_1based: int) -> str:
    if not _OCR_AVAILABLE:
        return ""
    images = convert_from_path(pdf_path, first_page=page_number_1based, last_page=page_number_1based)
    if not images:
        return ""
    return pytesseract.image_to_string(images[0])


def parse_pdf(pdf_path: str, doc_id: str, version: int) -> Node:
    root = Node(
        id=f"{doc_id}:v{version}:root",
        doc_id=doc_id, version=version, node_type="document",
        heading_number=None, heading_text="ROOT", level=0, order_index=-1,
        parent_id=None, body_text="",
    )
    root.content_hash = root.compute_hash()

    order_counter = 0
    stack = [root]  # stack of open ancestors, indexable by depth

    with pdfplumber.open(pdf_path) as pdf:
        # Pre-scan to estimate the document's body font size once, globally.
        all_lines_by_page = []
        for page in pdf.pages:
            chars = page.chars
            all_lines_by_page.append(_group_chars_into_lines(chars))
        flat_lines = [l for page_lines in all_lines_by_page for l in page_lines]
        body_size = _estimate_body_font_size(flat_lines)

    paragraph_buffer = []
    paragraph_is_list = False
    paragraph_start_page = [None]  # mutable box so the closure can update it
    LIST_ITEM_START_RE = re.compile(r"^\d+\.\s")

    def flush_paragraph():
        nonlocal paragraph_buffer, order_counter, paragraph_is_list
        if not paragraph_buffer:
            return
        text = normalize_text(" ".join(paragraph_buffer))
        is_list = paragraph_is_list
        start_page = paragraph_start_page[0]
        paragraph_buffer = []
        paragraph_is_list = False
        paragraph_start_page[0] = None
        if not text:
            return
        order_counter += 1
        parent = stack[-1]
        node = Node(
            id=f"{doc_id}:v{version}:n{order_counter}",
            doc_id=doc_id, version=version,
            node_type="list_item" if is_list else "paragraph",
            heading_number=None, heading_text=None,
            level=parent.level + 1, order_index=order_counter,
            parent_id=parent.id, body_text=text,
            page_number=start_page,
        )
        node.content_hash = node.compute_hash()
        parent.children.append(node)

    for page_idx, page in enumerate(pdf.pages, start=1):
            page_has_text = len(page.chars) > 0

            if not page_has_text:
                # OCR fallback: whole page becomes one reviewable paragraph node.
                text = _ocr_page_text(pdf_path, page_idx).strip()
                if text:
                    order_counter += 1
                    parent = stack[-1]
                    node = Node(
                        id=f"{doc_id}:v{version}:p{page_idx}:ocr{order_counter}",
                        doc_id=doc_id, version=version, node_type="paragraph",
                        heading_number=None, heading_text=None,
                        level=parent.level + 1, order_index=order_counter,
                        parent_id=parent.id, body_text=text,
                        page_number=page_idx, source="ocr", needs_review=True,
                    )
                    node.content_hash = node.compute_hash()
                    parent.children.append(node)
                continue

            # ---- collect tables (with position + rows) so they can be interleaved ----
            page_tables = []
            try:
                for t in page.find_tables():
                    page_tables.append({"top": t.bbox[1], "bbox": t.bbox, "rows": t.extract()})
            except Exception:
                page_tables = []

            lines = all_lines_by_page[page_idx - 1]

            def in_table(line_chars):
                x0 = min(c["x0"] for c in line_chars)
                top = min(c["top"] for c in line_chars)
                for tb in page_tables:
                    bx0, btop, bx1, bbtm = tb["bbox"]
                    if bx0 - 2 <= x0 <= bx1 + 2 and btop - 2 <= top <= bbtm + 2:
                        return True
                return False

            # Build a single top-to-bottom event stream: ("line", top, chars) / ("table", top, table_dict)
            events = [("line", min(c["top"] for c in lc), lc) for lc in lines if not in_table(lc)]
            events += [("table", tb["top"], tb) for tb in page_tables]
            events.sort(key=lambda e: e[1])

            for kind, _top, payload in events:
                if kind == "table":
                    flush_paragraph()
                    order_counter += 1
                    parent = stack[-1]
                    clean_rows = [[(cell or "").strip() for cell in row] for row in payload["rows"]]
                    node = Node(
                        id=f"{doc_id}:v{version}:tbl{order_counter}",
                        doc_id=doc_id, version=version, node_type="table",
                        heading_number=None, heading_text=None,
                        level=parent.level + 1, order_index=order_counter,
                        parent_id=parent.id, body_text="",
                        table_rows=clean_rows, page_number=page_idx,
                    )
                    node.content_hash = node.compute_hash()
                    parent.children.append(node)
                    continue

                line_chars = payload
                text = "".join(c["text"] for c in line_chars).strip()
                if not text:
                    continue
                size, bold = _line_font_info(line_chars)

                m = HEADING_RE.match(text)
                # Boldness is the primary heading signal (defeats the classification
                # list under 3.3, which matches the numbering regex but is NOT bold).
                # Size is a secondary, non-blocking sanity check only for level-1 headings.
                is_heading = bool(m) and bold

                if is_heading:
                    flush_paragraph()
                    number, title = m.group(1), m.group(2)
                    depth = number.count(".") + 1
                    order_counter += 1

                    while len(stack) > 1 and stack[-1].level >= depth:
                        stack.pop()
                    parent = stack[-1]
                    skipped = depth - parent.level > 1

                    node = Node(
                        id=f"{doc_id}:v{version}:sec{number}",
                        doc_id=doc_id, version=version, node_type="section",
                        heading_number=number, heading_text=title,
                        level=depth, order_index=order_counter,
                        parent_id=parent.id, body_text="",
                        page_number=page_idx, skipped_levels=skipped,
                    )
                    node.content_hash = node.compute_hash()
                    parent.children.append(node)
                    stack.append(node)
                else:
                    if LIST_ITEM_START_RE.match(text) and stack[-1].node_type == "section":
                        flush_paragraph()
                        paragraph_is_list = True
                    if not paragraph_buffer:
                        paragraph_start_page[0] = page_idx
                    paragraph_buffer.append(text)
            # NOTE: no flush here -- a paragraph may continue on the next page.
            # We only flush at the very end of the document, or when a heading/
            # table/list-item boundary is hit (handled above).

    flush_paragraph()  # flush whatever's left after the last page
    _merge_split_tables(root)
    return root


def _merge_split_tables(node: Node) -> None:
   
    i = 0
    children = node.children
    while i < len(children) - 1:
        a, b = children[i], children[i + 1]
        if (a.node_type == "table" and b.node_type == "table"
                and a.table_rows and b.table_rows
                and len(a.table_rows[0]) == len(b.table_rows[0])):
            a.table_rows = a.table_rows + b.table_rows
            a.content_hash = a.compute_hash()
            del children[i + 1]
            continue  # re-check in case a third fragment follows
        i += 1
    for c in node.children:
        _merge_split_tables(c)


def flatten(node: Node) -> list[Node]:
    out = [node]
    for c in node.children:
        out.extend(flatten(c))
    return out
