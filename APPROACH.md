# Approach Document

## 0. Environment constraint that shaped this submission

This was built in a sandbox with **no network access** at all (no `pip
install`, no Mongo Atlas, no live LLM calls). I made two calls given that:

1. I generated `data/ct200_manual_v1.pdf` and `data/ct200_manual_v2.pdf`
   myself from the manual text in the assignment, using `reportlab`
   (`scripts/gen_pdfs.py`), so that "OCR-based document extraction" has a
   real PDF to run against rather than being untestable. I controlled
   font/style per block type (heading levels, list items, tables) — but
   deliberately preserved every structural irregularity actually present in
   the source text (see §2) rather than "cleaning" them away. I did **not**
   design the parser around knowing the fixture's internal styling; the
   heading classifier only sees font-size/boldness and text content, the
   same signals it would get from a real scanned/exported PDF.
2. `fastapi`/`sqlalchemy`/`pydantic` were not installable, so I could not
   run the API layer. I wrote it fully and carefully, but it is genuinely
   untested beyond `py_compile`. The parser and version-matcher — the parts
   the assignment weights most heavily — **are** fully run and unit-tested
   against the real PDFs. I'd rather be upfront about exactly where the
   line is than pretend the whole thing was verified.

## 1. OCR / document parsing approach

`app/parsing/pdf_parser.py`. Text-layer extraction via `pdfplumber` first
(gives per-character font size/boldness/position, which text-only libraries
like `pypdf` don't). If a page has zero extractable characters (a scanned
image), we fall back to OCR for that page only (`pdf2image` + `pytesseract`),
and mark nodes from that page `source="ocr"`, `needs_review=True` rather
than pretending OCR text has the same reliability as a text layer. This
hybrid approach reflects how a real regulated-document pipeline usually
looks: text layer where available (fast, accurate), OCR as a documented
fallback (slower, needs review), not "OCR everything" or "assume every PDF
has a clean text layer."

**Heading detection is a classifier, not a hardcoded pattern.** A line is a
heading candidate only if it matches a numbering regex (`N`, `N.N`, up to
`N.N.N.N`) **and** is rendered bold. Boldness, not font size, is the primary
signal — see §2 for why size alone fails.

**Hierarchy construction** uses a depth stack, walking the document in true
top-to-bottom, page-by-page order (not sorted by heading number). A new
heading pops the stack down to the nearest ancestor with a smaller depth,
then pushes itself. This means physically out-of-order headings (§2) are
preserved as-is; the tree reflects what's actually on the page.

## 2. Structural irregularities discovered, and how

I inspected the raw manual text manually first, then validated everything
by actually running the parser and printing the tree — the bugs below were
each caught this way, not anticipated in advance. That's the debugging
methodology throughout: build, print the real output, compare against the
source text, fix, re-run.

| Irregularity | What broke initially | Fix |
|---|---|---|
| A numbered classification list ("1. Normal", "2. Elevated", ... "5. Hypertensive Crisis") sits inside §3.3 and reuses digits 1-5, which collide with the top-level section numbers 1-8. | A regex-only heading detector would create 5 bogus duplicate top-level sections. | Require boldness (not just regex match) to count as a heading. The list is body-weight text, so it's correctly classified as `list_item` children of §3.3. **Also** initially the entire numbered list silently merged into the *preceding* paragraph's text (no node boundary at all) because paragraph-flushing only happened at headings/tables — found by printing a node and seeing "...at time of manufacture. 1. Normal: ... 5. Hypertensive Crisis..." concatenated into ONE paragraph. Fixed by detecting a list-item line boundary mid-stream and flushing before/after it. |
| Top-level headings use a literal period ("1. Device Overview") while sub-headings don't ("1.1 Intended Use"). | My first regex (`\d+(\.\d+)*\s+...`) didn't match the trailing period, so **every level-1 heading was invisible** and got swallowed into the previous section's body as a mis-indented paragraph. | Made the trailing period optional: `\d+(\.\d+){0,4}\.?\s+...`. |
| §3.4 (Auto Shutoff) physically appears **before** §3.3 (Result Display and Classification) in the document. | N/A — this was intentional in the fixture and correctly NOT "fixed" by the parser. | Order preserved via document-order traversal + `order_index`; both still correctly parent under §3. Verified with `test_out_of_order_headings_preserve_document_order_and_correct_parent`. |
| "2.1.1.1 Battery Life Under Typical Use" jumps straight from depth-2 (2.1) to depth-4, skipping depth-3 entirely. | Initially this heading style (10.5pt) fell just under my size-delta threshold (body+0.9pt) and wasn't detected as a heading at all — it silently became a run-on paragraph fragment. Found by diffing printed output against source text. | Dropped the size-delta requirement; boldness is now the sole heading signal (size is no longer load-bearing). The depth-4 node is parented under 2.1 (nearest shallower ancestor) and flagged `skipped_levels=True` so a reviewer can see the anomaly instead of it looking like ordinary nesting. |
| The Error Codes table (§4.2) straddles a page break. | `pdfplumber.find_tables()` works per-page, so the table came back as two separate table objects (a 6-row fragment + a 2-row fragment) attached to two different parents. | Post-process merge pass (`_merge_split_tables`) that combines adjacent same-parent table siblings with matching column counts. **Known limitation:** this would incorrectly merge two genuinely distinct same-width tables placed back-to-back with nothing between them — I accept that risk for this document rather than build a more elaborate table-continuation heuristic (e.g. "does row 1 of fragment 2 look like a header row") given the time budget. |
| A table appearing earlier on a page, followed by a heading later on the *same* page. | My first implementation processed all text lines for a page, then attached all tables found on that page to "whichever section is currently open" — i.e., **after** the last heading on the page, not the section the table actually followed. The 2.1 General Specifications table got mis-parented under 2.2 Cuff Specifications. Found by inspecting the tree and noticing the wrong table under the wrong heading. | Rebuilt per-page processing as a single top-to-bottom event stream (lines + tables sorted by vertical position) instead of two separate passes, so a table is attached to whichever section was open *at that point in the stream*. |
| A paragraph's text is split across a page boundary. | Paragraph buffer was page-scoped, so a paragraph that continues onto the next page got emitted as two separate `paragraph` nodes instead of one. Found in §2.2's output: two nodes where there should be one. | Hoisted the paragraph buffer outside the per-page loop; it now only flushes on a heading/table/list boundary or end-of-document, never on a page boundary by itself. |
| Non-ASCII characters (`≥`, `≤`, en/em dashes) in the source manual text. | Using named HTML entities (`&ge;`) that ReportLab's restricted XML parser doesn't recognize produced mojibake (`‡‡`) in the rendered PDF, which then corrupted line-grouping in the parser (two list items merged onto what looked like one visual line). This was a bug in **my fixture generator**, not a genuine document trait worth preserving, so I fixed it at the source (registered a Unicode TTF font, used numeric character references) rather than teaching the parser to cope with garbled glyphs that wouldn't occur in a real PDF. | See `scripts/gen_pdfs.py`. |

All five of these are covered by explicit unit tests in `tests/test_parser.py`
(duplicate-heading collision, out-of-order headings, skip-level heading,
split-table merge, cross-version hash stability) plus five more in
`tests/test_matcher.py` validating the version-matching behavior against the
real v1→v2 diff. **All 10 pass** (`python3 tests/test_parser.py` /
`test_matcher.py`).

### What I did NOT fully solve (and would with more time)
- The table-merge heuristic (column-count + adjacency) has the known false-
  positive risk described above.
- OCR-page paragraph buffering: if a page requiring OCR fallback interrupts
  a paragraph that started on a text-layer page, the buffer isn't carried
  across that boundary (unlike the text-layer-to-text-layer case, which is
  handled). Not exercised by the current fixtures since none of them are
  scanned images, but it's a real gap.
- List items are assumed single-paragraph; a wrapped multi-line list item
  works (subsequent non-list-starting lines keep accumulating into the open
  list buffer), but nested lists (a list item containing a sub-list) are not
  handled — none occur in this document.

## 3. Data model

- **Document** — logical container, keyed by `document_name`.
- **DocumentVersion** — one row per ingestion; `(document_id,
  version_number)` unique.
- **NodeRow** — one row per parsed tree node, always belongs to exactly one
  `DocumentVersion`, **immutable once written**. Has `heading_number`,
  `heading_text`, `level`, `order_index`, `parent_id` (within the same
  version), `body_text`, `table_rows_json`, `content_hash`.
- **LogicalNode** — cross-version identity. Every `NodeRow.logical_id`
  points here. This is the thing that makes "is this the same node across
  versions" a first-class concept instead of an ad-hoc join.
- **Selection** / **SelectionItem** — a named set of `(node_id,
  version_id)` pairs. Because `node_id` is a specific immutable `NodeRow`
  primary key, a Selection can never be affected by a later re-ingestion —
  there's nothing to re-resolve.

Why split NodeRow (version-pinned, immutable) from LogicalNode
(cross-version identity) instead of one mutable Node table with a "current
version" pointer: mutating a Node's content in place on re-ingestion would
make old Selections silently point at NEW text, which directly violates the
"selections must resolve to the exact text they were created against"
requirement. Keeping every version's nodes as distinct, permanent rows is
the only way to make that guarantee true by construction rather than by
convention.

## 4. Version-matching strategy (and where it breaks)

See `app/versioning/matcher.py` docstring for the full reasoning; summary:

1. **Sections** matched primarily by `heading_number` (stable identifier a
   reader actually refers to).
2. **Fallback**: fuzzy title similarity (difflib, threshold 0.75) for
   numbers that disappear/appear between versions, to catch renumbering.
3. **Non-section children** (paragraphs/lists/tables) matched *positionally*
   within a matched section pair — first paragraph↔first paragraph, etc.
4. "Changed" = `content_hash` inequality. Binary, content-blind.

**Where this breaks:**
- Positional child matching breaks if a paragraph is inserted or deleted in
  the *middle* of a section's own direct children — every subsequent
  paragraph in that section shifts alignment by one and gets flagged
  "changed" even if its text is byte-identical, because it's now being
  compared against the wrong sibling. A production version would need
  paragraph-level content similarity matching (e.g. same difflib approach
  used for section titles) rather than pure position.
- Fuzzy title matching can misfire if two genuinely different sections
  happen to have similar titles (e.g. "Cleaning Instructions" vs "Cleaning
  Procedure" in two different sections) — greedy best-match-first reduces
  but doesn't eliminate this.
- If a section is deleted in vN and a **new, unrelated** section happens to
  get the same number reused in vN+1 (unlikely in a real regulated doc, but
  not impossible), the number-match path would incorrectly treat them as
  the same logical node. We do not attempt content-similarity confirmation
  on top of number match — that's a real gap for a system deciding
  "same-number ⇒ same identity" with no sanity check.

## 5. LLM prompt design + structured-output strategy

`app/llm/client.py`. Prompt asks for **only** a JSON object matching a
pydantic schema (`title`, `steps`, `expected_result`, `risk_level`, 3-5
items). On the client side:

1. Best-effort extraction of a JSON object from the raw response (strips
   code fences / surrounding prose, since models often add these despite
   instructions).
2. `pydantic` validation against `TestCaseList`.
3. On failure: retry (default `MAX_RETRIES=2`) with a **repair prompt**
   that includes the previous malformed output and the exact validation
   error, rather than just re-sending the original prompt — the theory
   being "here's what you did wrong" converges faster than "try again."
4. If still invalid after retries: **do not crash, do not silently drop.**
   Persist a `status="failed"` record with the raw responses and the
   validation error, visible via `GET /retrieve/by-selection/{id}`. This
   is the explicit answer to "your system will get back a malformed
   response at some point — decide how it behaves": it behaves
   *observably*, not silently.

`MockLLMClient` provides deterministic, rule-based output (keyed off error
codes and numeric thresholds present in the selected text) so the entire
pipeline is exercisable offline with no API key — this is what
`scripts/demo_flow.sh` exercises by default.

## 6. Decision log (required)

**What's the one part of this system most likely to silently give wrong
results without erroring? How would you catch it?**
The positional child-matcher (§4). If someone edits a section by inserting
a new paragraph before an existing one, every downstream paragraph in that
section will be reported as "changed" — not an error, just a wrong (too
broad) staleness signal that looks perfectly plausible. I'd catch it by
adding a regression test that specifically inserts content mid-section
(not just edits-in-place, which is all my current fixture exercises) and
asserting only the actually-new paragraph is flagged new, not a cascade of
false "changed" flags on unrelated siblings.

**Where did you choose simplicity over correctness because of time, and
what would break first if this went to production as-is?**
Positional child matching itself (§4) is the clearest example: byte-content
matching (or even just fuzzy-matching each paragraph's text, the same way I
did for section titles) would be materially more correct but I didn't have
time to validate it against enough real edge cases to trust it. In
production, this would break first on any document where a human editor
inserts or deletes a sentence/paragraph in the middle of a section (which
is... most real edits) — staleness flags would over-fire on unrelated
content and erode trust in the feature faster than under-firing would.

**Name one input you did not handle, and what your system does when it
sees it.**
A page that fails BOTH text-layer extraction and OCR (e.g. blank page, or a
page pdf2image/tesseract can't process due to missing system deps in a
given deployment). Currently: `_ocr_page_text` returns an empty string, and
since I only create a node when `text.strip()` is non-empty, that page
silently contributes **zero nodes** — the content, if any existed, is lost
with no flag at all. This is the one place in the parser where I don't
follow my own "expose failures, don't silently drop content" principle,
and I'd fix it by emitting a `node_type="unparsed_page"` placeholder node
with `needs_review=True` instead of just skipping the page.

## 7. What I'd do differently with more time

1. Get a real environment (network access) and actually run the FastAPI/
   SQLAlchemy layer end-to-end — right now it's a careful, complete design
   that hasn't met a real interpreter for its dependencies. I'd expect a
   handful of small bugs (SQLAlchemy 2.0 API nuances, FastAPI dependency
   plumbing) surfacing immediately, the same way real bugs surfaced the
   moment I actually ran the parser instead of just reading it.
2. Replace positional child-matching with content-similarity matching
   (§4/§6) — same difflib approach already used for section titles, applied
   one level down.
3. Add the `unparsed_page` placeholder node described in §6 instead of
   silently dropping unreadable pages.
4. A slightly smarter staleness signal than pure hash-equality — e.g.
   flag *numeric* changes (thresholds, error codes, timing values) as
   high-severity and pure prose/wording changes as low-severity, using a
   regex pass over the diff rather than pretending all changes are equal.
   I did not attempt this because "how much does a number matter clinically"
   is exactly the kind of judgment call that shouldn't be automated without
   real domain review — but a severity *hint* (not a decision) would still
   be useful and honest about being a heuristic.
