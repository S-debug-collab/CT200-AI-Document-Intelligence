
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parsing.pdf_parser import parse_pdf, flatten  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
V1 = os.path.join(DATA_DIR, "ct200_manual_v1.pdf")
V2 = os.path.join(DATA_DIR, "ct200_manual_v2.pdf")


def _sections_by_number(root):
    return {n.heading_number: n for n in flatten(root) if n.node_type == "section"}


def test_numbered_classification_list_is_not_promoted_to_sections():
  
    root = parse_pdf(V1, "ct200", 1)
    sections = _sections_by_number(root)

    top_level_numbers = [n for n in sections if "." not in n]
    assert sorted(top_level_numbers, key=int) == [str(i) for i in range(1, 9)], (
        f"expected exactly one top-level section for numbers 1-8, got {top_level_numbers}"
    )

    sec_3_3 = sections["3.3"]
    list_items = [c for c in sec_3_3.children if c.node_type == "list_item"]
    assert len(list_items) == 5, f"expected 5 classification list items under 3.3, got {len(list_items)}"
    assert list_items[0].body_text.startswith("1. Normal")
    assert list_items[-1].body_text.startswith("5. Hypertensive Crisis")
    # None of them should have been mis-classified as sections.
    assert all(c.node_type != "section" for c in sec_3_3.children if "Normal" in c.body_text or "Elevated" in c.body_text)


def test_out_of_order_headings_preserve_document_order_and_correct_parent():
   
    root = parse_pdf(V1, "ct200", 1)
    sections = _sections_by_number(root)
    sec_3_3, sec_3_4 = sections["3.3"], sections["3.4"]
    sec_3 = sections["3"]

    assert sec_3_4.order_index < sec_3_3.order_index, "3.4 appears before 3.3 in the document and order_index must reflect that"
    assert sec_3_3.parent_id == sec_3.id
    assert sec_3_4.parent_id == sec_3.id
    assert sec_3_3.id != sec_3_4.id  # distinct node identities, not merged


def test_skip_level_heading_is_parented_correctly_and_flagged():
 
    root = parse_pdf(V1, "ct200", 1)
    sections = _sections_by_number(root)
    battery = sections["2.1.1.1"]
    sec_2_1 = sections["2.1"]

    assert battery.parent_id == sec_2_1.id
    assert battery.level == 4
    assert battery.skipped_levels is True


def test_page_spanning_table_is_merged_not_duplicated():
   
    root_v1 = parse_pdf(V1, "ct200", 1)
    sections_v1 = _sections_by_number(root_v1)
    tables_v1 = [c for c in sections_v1["4.2"].children if c.node_type == "table"]
    assert len(tables_v1) == 1, "expected the split table to be merged into a single table node"
    assert len(tables_v1[0].table_rows) == 6  # header + E1..E5

    root_v2 = parse_pdf(V2, "ct200", 2)
    sections_v2 = _sections_by_number(root_v2)
    tables_v2 = [c for c in sections_v2["4.2"].children if c.node_type == "table"]
    assert len(tables_v2) == 1
    assert len(tables_v2[0].table_rows) == 7  # header + E1..E6


def test_v2_content_changes_produce_different_hashes_for_same_logical_node():
   
    root_v1 = parse_pdf(V1, "ct200", 1)
    root_v2 = parse_pdf(V2, "ct200", 2)
    n1 = _sections_by_number(root_v1)["2.1.1.1"]
    n2 = _sections_by_number(root_v2)["2.1.1.1"]
    body_v1 = [c for c in n1.children if c.node_type == "paragraph"][0]
    body_v2 = [c for c in n2.children if c.node_type == "paragraph"][0]
    assert body_v1.content_hash != body_v2.content_hash

    # Meanwhile an unrelated, unchanged section (1.1 Intended Use) must hash IDENTICALLY.
    unchanged_v1 = _sections_by_number(root_v1)["1.1"]
    unchanged_v2 = _sections_by_number(root_v2)["1.1"]
    body_u1 = [c for c in unchanged_v1.children if c.node_type == "paragraph"][0]
    body_u2 = [c for c in unchanged_v2.children if c.node_type == "paragraph"][0]
    assert body_u1.content_hash == body_u2.content_hash


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL", fn.__name__, "->", e)
            failed += 1
        except Exception as e:
            print("ERROR", fn.__name__, "->", repr(e))
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
