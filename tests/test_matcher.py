import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parsing.pdf_parser import parse_pdf  # noqa: E402
from app.versioning.matcher import match_sections, full_diff  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
V1 = parse_pdf(os.path.join(DATA_DIR, "ct200_manual_v1.pdf"), "ct200", 1)
V2 = parse_pdf(os.path.join(DATA_DIR, "ct200_manual_v2.pdf"), "ct200", 2)


def _by_number(pairs):
    out = {}
    for m in pairs:
        num = m.old_node.heading_number if m.old_node else m.new_node.heading_number
        out[num] = m
    return out


def test_known_changed_sections_are_flagged_changed():
    matches = _by_number(match_sections(V1, V2))
    for num in ["2.1.1.1", "3.2", "4.2", "4.3"]:
        assert matches[num].status == "changed", f"expected {num} to be flagged changed"


def test_known_unchanged_sections_are_flagged_unchanged():
    matches = _by_number(match_sections(V1, V2))
    for num in ["1.1", "1.2", "2.2", "3.1", "3.3", "3.4", "6.1", "6.2", "7.1", "7.2", "8.1"]:
        assert matches[num].status == "unchanged", f"expected {num} to be unchanged"


def test_new_section_5_3_detected_with_no_old_node():
    matches = _by_number(match_sections(V1, V2))
    m = matches["5.3"]
    assert m.status == "new"
    assert m.old_node is None
    assert m.new_node is not None
    assert m.new_node.heading_text == "Data Export"


def test_out_of_order_3_3_and_3_4_both_match_correctly_across_versions():
   
    matches = _by_number(match_sections(V1, V2))
    m33, m34 = matches["3.3"], matches["3.4"]
    assert m33.old_node.heading_number == "3.3" and m33.new_node.heading_number == "3.3"
    assert m34.old_node.heading_number == "3.4" and m34.new_node.heading_number == "3.4"


def test_positional_child_match_flags_the_specific_changed_paragraph():
   
    diffs = full_diff(V1, V2)
    child_changes = [
        m for m in diffs
        if m.match_method == "positional"
        and m.old_node is not None and m.new_node is not None
        and m.old_node.parent_id and "sec3.2" in m.old_node.parent_id
    ]
    assert len(child_changes) == 1
    assert child_changes[0].status == "changed"
    assert "40 mmHg" in child_changes[0].old_node.body_text
    assert "30 mmHg" in child_changes[0].new_node.body_text


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
