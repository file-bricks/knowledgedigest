# KnowledgeDigest -- Standalone Knowledge Database with LLM Pre-Processing

A standalone knowledge database that doesn't just index documents -- it **understands** them.
Drop documents in, they get chunked, summarized by LLM (Haiku), deduplicated, and stored
in a searchable SQLite database. Originals are archived after processing.

## How It Works

```
Document dropped into inbox/
    |
    v
[1] Detection: file type, language, size
    |
    v
[2] Extraction: text from PDF/DOCX/HTML (OCR if needed)
    |
    v
[3] Chunking: split into logical sections (~350 words each)
    |
    v
[4] Summarization: Haiku LLM processes each chunk
    - 3-5 sentence summary per section
    - Keyword extraction
    - Domain/topic classification
    |
    v
[5] Deduplication: does this knowledge already exist?
    - Yes: MERGE with existing entry (don't duplicate)
    - No: create new knowledge node
    - Contradictions: flag explicitly (never delete)
    |
    v
[6] Archival: original document moves to archive/
    - Chunks and summaries stay in DB
    - Original retrievable on demand
    |
    v
[7] Query: search via CLI, API, or GUI
```

## Architecture

KnowledgeDigest is a **standalone knowledge base** with its own SQLite database (`knowledge.db`).
It is inspired by the document processing pipeline from the
[Epstein Document Analysis](https://en.wikipedia.org/wiki/Epstein_documents) project,
which processes millions of pages through a 7-phase pipeline with LLM fact extraction
and semantic deduplication.

### Core Principle

Raw documents are transformed into structured, deduplicated knowledge through
LLM-powered summarization. The system achieves roughly **8x data reduction**
(e.g., 385,000 text chunks -> ~115,000 unique facts) while preserving all
source references and explicitly flagging contradictions.

## Features

- **7-Phase Pipeline**: Detection -> Extraction -> Chunking -> Summarization -> Deduplication -> Archival -> Query
- **LLM Summarization**: Haiku processes each chunk into structured summaries with keywords and domain tags
- **Semantic Deduplication**: Exact match (subject+predicate+object) and near-duplicate detection (embedding similarity >0.92)
- **Contradiction Tracking**: Conflicting information is flagged, never silently merged
- **FTS5 Full-Text Search**: SQLite FTS5 with BM25 ranking and snippet highlighting
- **Zero External Dependencies**: Pure Python stdlib (sqlite3, pathlib, hashlib)
- **Multiple Interfaces**: CLI, Python API, SQLite direct access (GUI planned)

## Current Status

### Implemented (v0.1.0)
- FTS5-based search engine with BM25 ranking
- Chunking algorithm (350 words/chunk, sentence-boundary splitting)
- Keyword extraction (frequency-based, stopword filtering DE/EN)
- Skill indexing: 766 documents, 1,523 chunks, 6,627 keywords
- Wiki indexing: 413 documents, 567 chunks, 4,691 keywords
- Total: **1,179 documents, 2,090 chunks, 514,041 words** in 19.4 MB

### Planned
- Document ingestion pipeline (inbox/ -> processing -> archive/)
- PDF/DOCX text extraction (via ProFiler OCR engine)
- LLM summarization (Haiku batch processing)
- Semantic deduplication (embedding-based)
- Knowledge node consolidation
- Web GUI (SQLiteViewer-based or custom)
- REST API for external access
- CLI query interface (`kd search "topic"`, `kd ingest file.pdf`)

## Interfaces (Planned)

| Interface | Description | Status |
|---|---|---|
| **CLI** | `kd search`, `kd ingest`, `kd status` | Partial (search works) |
| **Python API** | `KnowledgeDigest.search()`, `.ingest()` | Partial (search works) |
| **Web GUI** | Browser-based search and browse | Planned |
| **SQLite Viewer** | Direct DB access via any SQLite tool | Works now |
| **REST API** | HTTP endpoints for external tools | Planned |

## Database Schema

```sql
-- Extracted full text
CREATE TABLE file_texts (
    file_id INTEGER PRIMARY KEY,
    full_text TEXT,
    language TEXT,          -- 'de', 'en', 'fr'
    extracted_at TEXT,
    method TEXT             -- 'pdf_text', 'ocr', 'docx', 'html'
);

-- LLM summaries (per chunk)
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    section_index INTEGER,
    summary TEXT,           -- 3-5 sentences
    keywords TEXT,          -- comma-separated
    domain TEXT,            -- topic/field
    created_at TEXT,
    model TEXT              -- 'haiku-4.5'
);

-- Knowledge nodes (deduplicated, consolidated)
CREATE TABLE knowledge_nodes (
    id INTEGER PRIMARY KEY,
    title TEXT,
    merged_summary TEXT,
    source_count INTEGER,
    domain TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Processing queue
CREATE TABLE digest_queue (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    status TEXT,            -- 'pending', 'extracting', 'summarizing',
                            -- 'deduplicating', 'done', 'error'
    created_at TEXT,
    finished_at TEXT,
    error_msg TEXT
);
```

## Cost Estimate (Initial Processing)

| Step | Count | Cost (Haiku) |
|---|---|---|
| PDF summarization | ~22,000 | ~$66 |
| DOCX summarization | ~4,000 | ~$12 |
| Deduplication | ~37,000 | ~$10 |
| Knowledge node generation | ~3,000 nodes | ~$9 |
| **Total (one-time)** | | **~$100** |

Ongoing costs: minimal (only new documents, individual Haiku calls).

## Integration

KnowledgeDigest is designed as a **standalone tool** that can optionally integrate
with other systems:

- **BACH**: Available as extension for the BACH agent system (skill/knowledge lookup)
- **Any LLM tool**: REST API allows any AI assistant to query the knowledge base
- **Direct SQLite**: Any SQLite-compatible tool can read the database

## Installation

```bash
pip install knowledgedigest  # planned
# or
git clone https://github.com/lukisch/knowledgedigest
cd knowledgedigest
pip install -e .
```

## Usage

```bash
# Index documents
kd ingest ~/documents/paper.pdf
kd ingest ~/documents/          # batch ingest entire folder

# Search
kd search "machine learning"
kd search --domain "physics" "dark energy"

# Status
kd status                       # show DB statistics
kd queue                        # show processing queue
```

```python
from knowledgedigest import KnowledgeDigest

kd = KnowledgeDigest("knowledge.db")
results = kd.search("quantum computing", limit=10)
for r in results:
    print(f"{r['title']}: {r['summary'][:100]}...")
```

## License

MIT License -- Copyright (c) 2026 Lukas Geiger

## Author

Lukas Geiger (github.com/lukisch)
