# KnowledgeDigest — Portable Knowledge Database with LLM Pre-Processing

> Standalone SQLite-based knowledge database. Drop documents in, they get chunked,
> summarized by LLM (Haiku), and stored in a fully-text-searchable database.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![SQLite FTS5](https://img.shields.io/badge/search-FTS5-green.svg)]()

---

🇩🇪 [Deutsche Dokumentation → README_de.md](README_de.md)

---

## What It Does

KnowledgeDigest transforms raw documents into a structured, searchable knowledge base:

```
Document (PDF/DOCX/TXT/MD/HTML)
    |
    v
[1] Text Extraction      — PDF, DOCX, HTML, TXT, Markdown
    |
    v
[2] Chunking             — ~500 words/chunk, sentence-boundary splits
    |
    v
[3] LLM Summarization    — Haiku: 3–5 sentence summary + keywords + domain tag
    |
    v
[4] FTS5 Indexing        — Full-text search with BM25 ranking
    |
    v
[5] Queue Management     — pending → processing → done
```

## Features

- **Zero external dependencies** — pure Python stdlib (sqlite3, pathlib, hashlib)
- **FTS5 full-text search** — BM25 ranking, snippet highlighting
- **LLM summarization queue** — batch-process documents with Claude Haiku
- **Multiple extractors** — PDF, DOCX, HTML, TXT, Markdown
- **Chunking engine** — sentence-boundary splitting, ~500 words/chunk
- **Domain tagging** — auto-classify documents by topic
- **Keyword extraction** — frequency-based, DE/EN stopword filtering
- **BACH integration** — skill indexer and wiki indexer included

## Current Status (v0.2.0)

| Metric | Value |
|--------|-------|
| Documents indexed | 9,016 |
| Text chunks | 106,268 |
| Total words | ~32 million |
| Keywords | 239,310 |
| FTS5 index | ✓ |
| LLM summaries | in progress (batch queue) |

## Installation

```bash
git clone https://github.com/lukisch/knowledgedigest
cd knowledgedigest
pip install -r requirements.txt
```

## Usage

```bash
# Ingest and index documents (recursive)
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest ingest /path/to/docs --recursive

# Unified full-text search (skills + wikis + documents)
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest search-all "your query"

# Status overview
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest status

# Batch summarization via LLM
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest summarize --limit 20
```

## Python API

```python
from KnowledgeDigest import KnowledgeDigest

kd = KnowledgeDigest()

# Search skills
results = kd.search("machine learning", limit=10)
for r in results:
    print(f"{r['skill_name']}: {r.get('snippet', '')[:100]}")

# Unified search (skills + wikis + documents)
results = kd.search_all("neural networks", limit=10)
for r in results:
    print(f"[{r['source']}] {r['name']}: {r.get('snippet', '')[:80]}")

# Ingest documents
kd.ingest("/path/to/documents/", recursive=True)

# Queue status
print(kd.get_queue_status())
```

## LLM Summarization Queue

KnowledgeDigest maintains a `digest_queue` table for batch LLM processing.
Each document starts as `pending` and moves to `done` after all chunks are summarized.

```python
import sqlite3

conn = sqlite3.connect("knowledge.db", timeout=30)

# Write a summary (per chunk)
conn.execute("""
    INSERT INTO summaries
        (source_type, source_id, chunk_index, summary, keywords, domain, model)
    VALUES ('document', ?, ?, ?, ?, ?, ?)
    ON CONFLICT(source_type, source_id, chunk_index) DO UPDATE SET
        summary=excluded.summary, keywords=excluded.keywords,
        domain=excluded.domain, model=excluded.model,
        created_at=CURRENT_TIMESTAMP
""", (doc_id, chunk_index, summary_text, keywords_csv, domain, model_name))
conn.commit()

# Mark document as done
conn.execute("""
    UPDATE digest_queue SET status='done', finished_at=CURRENT_TIMESTAMP
    WHERE source_type='document' AND source_id=? AND status IN ('pending','processing')
""", (doc_id,))
conn.commit()
```

## Architecture

```
knowledgedigest/
  schema.py        # DB schema v3 (31 tables)
  digest.py        # Main API class
  extractor.py     # Text extraction (PDF, DOCX, TXT, HTML, MD)
  chunker.py       # Text chunking (~500 tokens/chunk)
  summarizer.py    # LLM summarization (Haiku via API)
  indexer.py       # Skill indexer
  wiki_indexer.py  # Wiki indexer
  ingestor.py      # Document ingestion pipeline
  utils.py         # Shared utilities (SHA256, keywords, stopwords)
```

## Database Schema (Key Tables)

| Table | Contents |
|-------|----------|
| `documents` | File metadata (path, hash, type, size) |
| `document_chunks` | Text sections (~500 tokens each) |
| `document_keywords` | Per-document keywords |
| `document_fts` | FTS5 full-text index |
| `summaries` | LLM-generated summaries per chunk |
| `digest_queue` | Processing queue (pending/processing/done/error) |

## Integration

- **BACH agent system** — available as a skill/knowledge lookup extension
- **Any SQLite tool** — database is directly accessible
- **REST API** — planned for external tool access

## License

MIT License — Copyright (c) 2026 Lukas Geiger

## Author

Lukas Geiger ([github.com/lukisch](https://github.com/lukisch))
