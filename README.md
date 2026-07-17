# CT-200 Document Intelligence System

AI Engineering Internship Assignment - Tri9T AI

A FastAPI backend that ingests the CT-200 medical device manual, reconstructs its hierarchical structure, supports document versioning, generates QA test cases using an LLM, and detects stale traceability across document versions.

---

# Features

- PDF ingestion and hierarchy reconstruction
- OCR-based document extraction pipeline
- Document versioning (v1 → v2)
- Preservation of logical nodes across versions
- Browse document sections and nodes
- Search document content
- Version-pinned selections
- LLM-powered QA test case generation
- Structured LLM output validation
- Retrieval of generated test cases
- Node-level and generation-level staleness detection
- SQLite persistence for document structure
- MongoDB storage for generated outputs

---

# Tech Stack

- FastAPI
- SQLAlchemy
- SQLite
- MongoDB
- Pydantic
- Python
- PDFPlumber / PDF parsing tools
- OCR pipeline
- LLM API integration

---

# Project Structure

```
app/
│
├── api/
├── core/
├── llm/
├── models/
├── parsing/
├── schemas/
├── versioning/
└── main.py

data/
├── ct200_manual_v1.pdf
└── ct200_manual_v2.pdf

tests/

README.md
APPROACH.md
requirements.txt
.env.example
```

---

# Installation

Clone the repository:

```bash
git clone <repository-url>

cd <repository-folder>
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment:

## Windows

```bash
venv\Scripts\activate
```

## Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file using `.env.example`.

Example:

```env
DATABASE_URL=sqlite:///./ct200.db

MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=ct200

LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_API_KEY
```

---

# Running the Application

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

API Documentation:

Swagger UI:

```
http://127.0.0.1:8000/docs
```

ReDoc:

```
http://127.0.0.1:8000/redoc
```

Health Check:

```
GET /health
```

---

# End-to-End Demo Flow

## 1. Ingest Document Version 1

Upload the original CT-200 manual:

```
POST /ingest
```

Input:

```
data/ct200_manual_v1.pdf
```

The system:

- Extracts document content
- Builds hierarchy
- Stores nodes
- Generates content hashes
- Creates document version 1

---

## 2. Browse Document Structure

Retrieve sections:

```
GET /documents/{document_id}/sections
```

Retrieve a specific node:

```
GET /nodes/{node_id}
```

Returns:

- Heading
- Section level
- Parent relationship
- Body text
- Child nodes
- Content hash

---

## 3. Search Document

```
GET /documents/{document_id}/search?q=<keyword>
```

Searches across:

- Section headings
- Extracted document text

---

## 4. Create Version-Pinned Selection

```
POST /selections
```

Selections store:

- Selected node IDs
- Document version
- Exact source content reference

This ensures previous selections continue pointing to the original document version.

---

## 5. Generate QA Test Cases

```
POST /generate
```

The selected document content is sent to an LLM.

Generated output contains:

- Test case title
- Execution steps
- Expected result

LLM responses are validated using structured schemas.

Invalid responses are retried and rejected if validation continues failing.

---

## 6. Ingest Document Version 2

Upload:

```
data/ct200_manual_v2.pdf
```

The system:

- Creates a new document version
- Preserves version 1
- Matches unchanged logical nodes
- Detects modified sections

---

## 7. Detect Changes and Staleness

Node changes:

```
GET /nodes/{node_id}/staleness
```

Generated test case staleness:

```
GET /retrieve/{generation_id}/staleness
```

The system compares:

```
Original content hash
        |
        |
Current document content hash
```

If they differ, the generated QA test case is marked as potentially stale.

---

# API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ingest` | Ingest PDF document |
| GET | `/documents/{document_id}/sections` | List top-level sections |
| GET | `/nodes/{node_id}` | Retrieve node details |
| GET | `/documents/{document_id}/search` | Search document |
| GET | `/nodes/{node_id}/staleness` | Check node changes |
| POST | `/selections` | Create version-pinned selection |
| GET | `/selections/{selection_id}` | Retrieve selection |
| POST | `/generate` | Generate QA test cases |
| GET | `/retrieve/by-selection/{selection_id}` | Retrieve generated tests |
| GET | `/retrieve/by-node/{node_id}` | Retrieve tests by node |
| GET | `/retrieve/by-logical/{logical_id}` | Retrieve by logical node |
| GET | `/retrieve/{generation_id}/staleness` | Check generation staleness |
| GET | `/health` | Health check |

---

# Key Design Decisions

## PDF Extraction Approach

The system uses PDF parsing combined with OCR because engineering documents may contain:

- Machine-readable text
- Scanned pages
- Tables
- Irregular formatting

The goal is to preserve document structure rather than only extracting plain text.

---

## Hierarchy Reconstruction

The parser reconstructs:

```
Document
 |
 ├── Section
 |
 ├── Subsection
 |
 └── Paragraph
```

Each node stores:

- Node ID
- Heading
- Level
- Parent ID
- Body text
- Content hash

---

## Version Matching Strategy

Document versions are compared using:

- Section title similarity
- Parent-child structure
- Content hash comparison

Unchanged nodes are linked across versions.

Modified content is flagged for traceability impact analysis.

---

## LLM Generation Strategy

The LLM is instructed to return structured QA test cases.

Output validation is performed using Pydantic models.

If malformed output is received:

1. Retry generation
2. Validate response
3. Store failure information if retries fail

---

## Staleness Detection Strategy

Every generated QA test case stores:

- Source node IDs
- Document version
- Original content hashes

During retrieval, hashes are compared with the latest version.

If source requirements changed, the test cases are marked stale.

---

# Testing

Run:

```bash
pytest
```

Test coverage includes:

- PDF hierarchy extraction
- Parent-child relationship validation
- Duplicate heading handling
- Document version matching
- Modified content detection
- Staleness detection

---

# Decision Log

## 1. What part can silently give wrong results?

The hierarchy reconstruction process is the most likely to silently produce incorrect results because wrong parent-child relationships can still look valid.

Detection methods:

- Manual PDF comparison
- Validation scripts
- Unit tests for hierarchy cases

---

## 2. Where was simplicity chosen over correctness?

The version matching approach uses structural similarity and hashing instead of a full semantic document understanding model.

A more advanced embedding-based matcher could improve handling of heavily rewritten sections.

---

## 3. Unsupported input case

Very poor-quality scanned pages or handwritten annotations may not be extracted correctly.

The system exposes extraction limitations instead of silently generating incorrect document structures.

---

# Documentation

Additional details about:

- Parser implementation
- Hierarchy reconstruction
- Version matching strategy
- LLM prompt design
- Validation strategy
- Engineering decisions

are available in:

```
APPROACH.md
```
