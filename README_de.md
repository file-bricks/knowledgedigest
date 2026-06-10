# KnowledgeDigest — Portable Wissensdatenbank mit LLM-Vorverarbeitung

> Eigenständige SQLite-basierte Wissensdatenbank. Dokumente ablegen, automatisch indexieren,
> per LLM (Haiku) zusammenfassen und in einer volltextdurchsuchbaren Datenbank speichern.

---

🇬🇧 [English documentation → README.md](README.md)

---

## Was es macht

KnowledgeDigest wandelt Rohdokumente in eine strukturierte, durchsuchbare Wissensbasis um:

```
Dokument (PDF/DOCX/TXT/MD/HTML)
    |
    v
[1] Text-Extraktion      — PDF, DOCX, HTML, TXT, Markdown
    |
    v
[2] Chunking             — ~500 Wörter/Chunk, Satzgrenz-Splitting
    |
    v
[3] LLM-Summarization    — Haiku: 3–5 Satz-Summary + Keywords + Domain-Tag
    |
    v
[4] FTS5-Indexierung     — Volltextsuche mit BM25-Ranking
    |
    v
[5] Queue-Management     — pending → processing → done
```

## Funktionen

- **Keine externen Abhängigkeiten** — reines Python stdlib (sqlite3, pathlib, hashlib)
- **FTS5-Volltextsuche** — BM25-Ranking, Snippet-Highlighting
- **LLM-Summarization-Queue** — Batch-Verarbeitung mit Claude Haiku
- **Mehrere Extraktoren** — PDF, DOCX, HTML, TXT, Markdown
- **Chunking-Engine** — Satzgrenz-Splitting, ~500 Wörter/Chunk
- **Domain-Tagging** — automatische Klassifizierung nach Themengebiet
- **Keyword-Extraktion** — frequenzbasiert, DE/EN-Stoppwort-Filter
- **BACH-Integration** — Skill-Indexer und Wiki-Indexer inklusive

## Aktueller Stand (v0.2.0)

| Kennzahl | Wert |
|----------|------|
| Indexierte Dokumente | 9.016 |
| Text-Chunks | 106.268 |
| Gesamtwörter | ~32 Millionen |
| Keywords | 239.310 |
| FTS5-Index | ✓ |
| LLM-Summaries | in Bearbeitung (Batch-Queue) |

## Installation

```bash
git clone https://github.com/lukisch/knowledgedigest
cd knowledgedigest
pip install -r requirements.txt
```

## Nutzung

```bash
# Dokumente indexieren (rekursiv)
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest ingest /pfad/zu/docs --recursive

# Volltextsuche (Skills + Wikis + Dokumente)
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest search-all "Suchanfrage"

# Status-Übersicht
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest status

# Batch-Summarization per LLM
PYTHONIOENCODING=utf-8 python -m KnowledgeDigest summarize --limit 20
```

## Architektur

```
knowledgedigest/
  schema.py        # DB-Schema v3 (31 Tabellen)
  digest.py        # Haupt-API-Klasse
  extractor.py     # Text-Extraktion (PDF, DOCX, TXT, HTML, MD)
  chunker.py       # Text-Chunking (~500 Tokens/Chunk)
  summarizer.py    # LLM-Summarization (Haiku per API)
  indexer.py       # Skill-Indexer
  wiki_indexer.py  # Wiki-Indexer
  ingestor.py      # Dokument-Ingestion-Pipeline
  utils.py         # Shared Utilities (SHA256, Keywords, Stoppwörter)
```

## Lizenz

MIT License — Copyright (c) 2026 Lukas Geiger

## Autor

Lukas Geiger ([github.com/lukisch](https://github.com/lukisch))
