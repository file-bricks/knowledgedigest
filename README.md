# KnowledgeDigest -- Portable Knowledge Database

A portable, self-contained knowledge database that indexes documents, chunks them,
and makes them searchable via FTS5 full-text search. Optionally summarizes chunks
with LLM (Haiku). Two frontends: **PySide6 Desktop GUI** and **Web Viewer**.

## Quick Start

```bash
git clone https://github.com/lukisch/knowledgedigest
cd knowledgedigest
pip install -r requirements.txt

# Desktop GUI (PySide6, dark theme, 3-panel layout)
python -m KnowledgeDigest --gui

# Web Viewer (stdlib-only, dark theme, localhost:8787)
python -m KnowledgeDigest --web

# CLI
python -m KnowledgeDigest status
```

## How It Works

```
Add directories via GUI or config
    |
    v
[1] Detection: file type, language, size
    |
    v
[2] Extraction: text from PDF/DOCX/HTML/TXT/MD
    |
    v
[3] Chunking: split into sections (~350 words each)
    |
    v
[4] Indexing: FTS5 full-text search + keyword extraction
    |
    v
[5] Summarization (optional): Haiku LLM per chunk
    - 3-5 sentence summary
    - Keyword extraction
    - Domain classification
    |
    v
[6] Query: search via GUI, Web Viewer, CLI, or Python API
```

## Features

- **Portable**: JSON config, no hardcoded paths. Copy the folder, it works.
- **Two Frontends**: PySide6 Desktop GUI + stdlib Web Viewer
- **FTS5 Search**: SQLite FTS5 with BM25 ranking and snippet highlighting
- **Document Support**: PDF, DOCX, TXT, MD, HTML
- **LLM Summarization** (optional): Haiku batch processing per chunk
- **Directory Management**: Add/remove/scan directories via GUI or config
- **No LLM Required**: Indexing, search, and browsing work without any LLM

## Desktop GUI

3-panel splitter layout with dark theme:

| Panel | Content |
|-------|---------|
| **Left** | Indexed directories with document counts |
| **Center** | Document table (sortable, filterable) |
| **Right** | Preview (text, PDF via PyMuPDF, images, metadata) |

Toolbar: Add Directory, Scan, Search, Web Viewer, Settings

## Web Viewer

Standalone browser-based viewer (Python stdlib only, no dependencies):

- **Dashboard**: Document and summary statistics
- **Browse**: All documents with pagination
- **Search**: FTS5 full-text search with highlighting
- **Folders**: Browse by directory
- **Summaries**: LLM-generated summaries catalog
- **Document Detail**: Full chunk content, metadata, keywords

Startable standalone (`--web`) or from within the GUI (toolbar button).

## Interfaces

| Interface | Command | Status |
|-----------|---------|--------|
| **Desktop GUI** | `python -m KnowledgeDigest --gui` | v0.3.0 |
| **Web Viewer** | `python -m KnowledgeDigest --web` | v0.3.0 |
| **CLI** | `python -m KnowledgeDigest status` | v0.1.0+ |
| **Python API** | `from KnowledgeDigest import KnowledgeDigest` | v0.1.0+ |
| **SQLite Direct** | Any SQLite tool on `knowledge.db` | Always |

## Python API

```python
from KnowledgeDigest import KnowledgeDigest
from KnowledgeDigest.config import get_config

kd = KnowledgeDigest(config=get_config())

# Manage directories
kd.add_directory("/path/to/docs")
kd.scan_directory("/path/to/docs", recursive=True)

# Search
results = kd.search_all("machine learning", limit=10)
for r in results:
    print(f"{r['filename']}: {r['snippet'][:80]}...")

# Status
status = kd.get_status()
print(f"Documents: {status['documents']['total_documents']}")
print(f"Chunks: {status['documents']['total_chunks']}")
```

## Configuration

JSON-based config (`knowledgedigest.json`), searched in order:
1. `--config` CLI argument
2. Current working directory
3. Next to the database file
4. `%APPDATA%\KnowledgeDigest\` (Windows) / `~/.config/knowledgedigest/` (Linux)
5. Built-in defaults

All settings optional. Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `db_path` | `data/knowledge.db` | Database location |
| `indexed_directories` | `[]` | Directories to index |
| `chunk_size` | `350` | Words per chunk |
| `web_port` | `8787` | Web viewer port |
| `bach_enabled` | `false` | BACH system integration |

## BACH Integration (Optional)

KnowledgeDigest can optionally integrate with the [BACH](https://github.com/lukisch) agent system.
When `bach_enabled: true` and `bach_db_path` is set, BACH skills and wiki articles
are indexed alongside regular documents. This integration is lazy-loaded and has
zero impact when disabled.

## Requirements

- Python 3.10+
- PySide6 (for GUI)
- PyMuPDF (for PDF preview in GUI)
- No additional dependencies for CLI or Web Viewer

## See Also: ProFiler

Need PDF encryption, OCR, anonymization, or file versioning? Check out [ProFiler](https://github.com/file-bricks/ProFiler) -- a professional file management suite from the same author.

| | KnowledgeDigest | ProFiler |
|---|---|---|
| **Focus** | Knowledge search, chunking, LLM summaries | File management, PDF tools, OCR, privacy |
| **Search** | FTS5 with BM25 ranking, snippet highlighting | Multi-DB, type/size/date filters |
| **AI** | LLM summarization (Haiku), keyword extraction | -- |
| **PDF** | Read-only (text extraction) | Encrypt, decrypt, extract, redact, OCR |
| **Privacy** | -- | Anonymization, redaction, clipboard guard |
| **Interfaces** | Desktop GUI, Web Viewer, CLI, Python API | Desktop GUI, System Tray |
| **License** | MIT | AGPL v3 |

## License

MIT License -- Copyright (c) 2026 Lukas Geiger

## Author

Lukas Geiger ([github.com/lukisch](https://github.com/lukisch))

> **Kein Rechts-/Steuer-/Anlage-Rat.** Dieses Projekt ist ein technisches Hilfswerkzeug, keine professionelle Beratung. Bei finanziellen, rechtlichen oder steuerlichen Entscheidungen konsultieren Sie qualifizierte Fachleute.
>
> **No legal/tax/investment advice.** This project is a technical tool, not professional advice. Consult qualified professionals for financial, legal, or tax decisions.


---

## Haftung / Liability

Dieses Projekt ist eine **unentgeltliche Open-Source-Schenkung** im Sinne der §§ 516 ff. BGB. Die Haftung des Urhebers ist gemäß **§ 521 BGB** auf **Vorsatz und grobe Fahrlässigkeit** beschränkt. Ergänzend gelten die Haftungsausschlüsse aus GPL-3.0 / MIT / Apache-2.0 §§ 15–16 (je nach gewählter Lizenz).

Nutzung auf eigenes Risiko. Keine Wartungszusage, keine Verfügbarkeitsgarantie, keine Gewähr für Fehlerfreiheit oder Eignung für einen bestimmten Zweck.

This project is an unpaid open-source donation. Liability is limited to intent and gross negligence (§ 521 German Civil Code). Use at your own risk. No warranty, no maintenance guarantee, no fitness-for-purpose assumed.

