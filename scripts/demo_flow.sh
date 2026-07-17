#!/usr/bin/env bash
# End-to-end demo of the versioning + staleness flow.
# Requires the API running locally: `uvicorn app.main:app --reload`
set -euo pipefail
BASE="${BASE_URL:-http://localhost:8000}"
DOC_NAME="ct200-manual"

echo "== 1. Ingest v1 =="
V1_RESP=$(curl -s -X POST "$BASE/ingest" -F "document_name=$DOC_NAME" -F "file=@data/ct200_manual_v1.pdf")
echo "$V1_RESP" | python3 -m json.tool
DOC_ID=$(echo "$V1_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['document_id'])")

echo -e "\n== 2. Browse top-level sections (latest = v1) =="
curl -s "$BASE/documents/$DOC_ID/sections" | python3 -m json.tool

echo -e "\n== 3. Search for 'overpressure' =="
curl -s "$BASE/documents/$DOC_ID/search?q=overpressure" | python3 -m json.tool

echo -e "\n== 4. Get node detail for section 4.1 (grab its id from step 2/3 output manually if needed) =="
NODE_ID=$(curl -s "$BASE/documents/$DOC_ID/search?q=Overpressure%20Protection" | python3 -c "import sys,json; r=json.load(sys.stdin); print(next(n['id'] for n in r if n['heading_number']=='4.1'))")
echo "node id: $NODE_ID"
curl -s "$BASE/nodes/$NODE_ID" | python3 -m json.tool

echo -e "\n== 5. Create a selection over section 4.1 + 4.2 (error codes) =="
NODE_4_2=$(curl -s "$BASE/documents/$DOC_ID/search?q=Error%20Codes" | python3 -c "import sys,json; r=json.load(sys.stdin); print(next(n['id'] for n in r if n['heading_number']=='4.2'))")
SEL_RESP=$(curl -s -X POST "$BASE/selections" -H "Content-Type: application/json" \
  -d "{\"document_id\": \"$DOC_ID\", \"name\": \"overpressure-and-errors\", \"node_ids\": [\"$NODE_ID\", \"$NODE_4_2\"]}")
echo "$SEL_RESP" | python3 -m json.tool
SEL_ID=$(echo "$SEL_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo -e "\n== 6. Generate QA test cases for the selection (uses MockLLMClient unless LLM_API_KEY is set) =="
GEN_RESP=$(curl -s -X POST "$BASE/generate" -H "Content-Type: application/json" -d "{\"selection_id\": \"$SEL_ID\"}")
echo "$GEN_RESP" | python3 -m json.tool
GEN_ID=$(echo "$GEN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo -e "\n== 7. Submit the SAME selection again -- should reuse the existing generation (idempotency policy) =="
curl -s -X POST "$BASE/generate" -H "Content-Type: application/json" -d "{\"selection_id\": \"$SEL_ID\"}" | python3 -m json.tool

echo -e "\n== 8. Retrieve generations by selection id =="
curl -s "$BASE/retrieve/by-selection/$SEL_ID" | python3 -m json.tool

echo -e "\n== 9. Check staleness BEFORE re-ingesting v2 (should be false) =="
curl -s "$BASE/retrieve/$GEN_ID/staleness" | python3 -m json.tool

echo -e "\n== 10. Re-ingest v2 (same document_name -> new version, v1 preserved) =="
curl -s -X POST "$BASE/ingest" -F "document_name=$DOC_NAME" -F "file=@data/ct200_manual_v2.pdf" | python3 -m json.tool

echo -e "\n== 11. Check staleness AFTER re-ingesting v2 (4.2's error table changed -> should be true, with a diff) =="
curl -s "$BASE/retrieve/$GEN_ID/staleness" | python3 -m json.tool

echo -e "\n== 12. Confirm v1 selection still resolves to the ORIGINAL v1 text (version-pinning proof) =="
curl -s "$BASE/nodes/$NODE_4_2" | python3 -c "import sys,json; n=json.load(sys.stdin); print('v1-pinned node still shows original text, no E6 row:'); print([r for r in n['table_rows'] if r])"

echo -e "\n== 13. Browse latest (v2) top-level sections -- should now include 5.3 Data Export =="
curl -s "$BASE/documents/$DOC_ID/sections?version=2" | python3 -m json.tool

echo -e "\nDone."
