# Tri9T CT-200 Document Intelligence API

A FastAPI backend that ingests the CT-200 medical device manual, reconstructs its hierarchical structure, supports document versioning, generates QA test cases using an LLM, and detects stale traceability across document versions.

---

## Features

- PDF ingestion and hierarchy reconstruction
- Document versioning (v1 → v2)
- Browse document sections and nodes
- Search document content
- Version-pinned selections
- LLM-powered QA test case generation
- Retrieval of generated test cases
- Staleness detection for nodes and generated test cases
- SQLite persistence
- MongoDB storage for generated outputs

---

## Tech Stack

- FastAPI
- SQLAlchemy
- SQLite
- MongoDB
- Pydantic
- PDFPlumber / OCR pipeline
- Python

---

## Project Structure

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
tests/
README.md
APPROACH.md
requirements.txt
```

---

## Installation

Clone the repository

```bash
git clone <repository-url>
cd <repository-folder>
```

Create a virtual environment

```bash
python -m venv venv
```

Activate the environment

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file.

Example:

```env
DATABASE_URL=sqlite:///./ct200.db

MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=ct200

LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_API_KEY
```

---

## Running the Application

Start the server

```bash
uvicorn app.main:app --reload
```

API Documentation

Swagger UI

```
http://127.0.0.1:8000/docs
```

ReDoc

```
http://127.0.0.1:8000/redoc
```

Health Check

```
GET /health
```

---

## Testing the Application

### 1. Ingest Version 1

Use

```
POST /ingest
```

Upload

```
data/ct200_manual_v1.pdf
```

---

### 2. Ingest Version 2

Upload

```
data/ct200_manual_v2.pdf
```

This creates a new version while preserving Version 1.

---

### 3. Browse Sections

```
GET /documents/{document_id}/sections
```

---

### 4. Get Node Details

```
GET /nodes/{node_id}
```

Returns

- Heading
- Body text
- Children
- Content hash
- Full reconstructed text

---

### 5. Search Document

```
GET /documents/{document_id}/search?q=...
```

---

### 6. Check Node Staleness

```
GET /nodes/{node_id}/staleness
```

---

### 7. Create Selection

```
POST /selections
```

Selections are version-pinned and always reference the exact document version used during creation.

---

### 8. Generate QA Test Cases

```
POST /generate
```

Generates QA test cases from the selected document sections.

---

### 9. Retrieve Generated Test Cases

```
GET /retrieve/by-selection/{selection_id}
```

or

```
GET /retrieve/by-node/{node_id}
```

---

### 10. Check Generation Staleness

```
GET /retrieve/{generation_id}/staleness
```

Determines whether previously generated test cases are still valid after document updates.

---

## API Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/ingest` | Ingest PDF |
| GET | `/documents/{document_id}/sections` | List top-level sections |
| GET | `/nodes/{node_id}` | Get node details |
| GET | `/documents/{document_id}/search` | Search document |
| GET | `/nodes/{node_id}/staleness` | Check node changes |
| POST | `/selections` | Create selection |
| GET | `/selections/{selection_id}` | Get selection |
| POST | `/generate` | Generate QA test cases |
| GET | `/retrieve/by-selection/{selection_id}` | Retrieve by selection |
| GET | `/retrieve/by-node/{node_id}` | Retrieve by node |
| GET | `/retrieve/by-logical/{logical_id}` | Retrieve by logical node |
| GET | `/retrieve/{generation_id}/staleness` | Generation staleness |
| GET | `/health` | Health check |

---

## Notes

- The system preserves document hierarchy during parsing.
- Every node stores a content hash used for change detection.
- Selections remain tied to the exact document version they were created from.
- Generated test cases are linked to the original document content to support traceability.
- Staleness detection identifies whether document updates affect previously generated QA test cases.

---

## Documentation

Additional implementation details, design decisions, parser strategy, version matching, and engineering decisions are documented in **APPROACH.md**.