# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- DB-Schema Definition + Migration.

Eigene SQLite-DB (knowledge.db) fuer indexierte BACH-Skills.
NICHT in bach.db schreiben!

Schema-Design v3:
    skill_index / skill_chunks / skill_fts / skill_keywords  -- BACH Skills
    wiki_index / wiki_chunks / wiki_fts / wiki_keywords      -- BACH Wikis
    documents / document_chunks / document_fts / document_keywords -- Ingested Docs
    summaries     -- LLM-Zusammenfassungen (quelluebergreifend)
    digest_queue  -- Processing Queue

Entscheidung: Normalisiertes Schema statt flache skill_knowledge Tabelle,
weil FTS5 ueber einzelne Chunks performanter ist als ueber JSON-Blobs.
"""

__all__ = ["SCHEMA_SQL", "SCHEMA_VERSION", "ensure_schema", "get_schema_version"]

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 3

SCHEMA_SQL = """
-- ========================================================================
-- SKILLS (BACH Skills aus bach.db)
-- ========================================================================

-- Skill-Metadaten (1 Zeile pro BACH-Skill)
CREATE TABLE IF NOT EXISTS skill_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT UNIQUE NOT NULL,
    skill_type TEXT NOT NULL,
    category TEXT,
    path TEXT,
    description TEXT,
    version TEXT,
    content_hash TEXT,
    word_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_db TEXT
);

-- Gechunkte Textabschnitte (N Zeilen pro Skill)
CREATE TABLE IF NOT EXISTS skill_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL REFERENCES skill_index(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    is_frontmatter INTEGER DEFAULT 0,
    UNIQUE(skill_id, chunk_index)
);

-- FTS5 Volltextindex ueber Chunks
CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(
    skill_name,
    content,
    tokenize='unicode61'
);

-- Trigger: skill_chunks -> skill_fts sync
CREATE TRIGGER IF NOT EXISTS chunk_ai AFTER INSERT ON skill_chunks BEGIN
    INSERT INTO skill_fts(rowid, skill_name, content)
    SELECT new.id,
           (SELECT skill_name FROM skill_index WHERE id = new.skill_id),
           new.content;
END;

CREATE TRIGGER IF NOT EXISTS chunk_ad AFTER DELETE ON skill_chunks BEGIN
    INSERT INTO skill_fts(skill_fts, rowid, skill_name, content)
    SELECT 'delete', old.id,
           (SELECT skill_name FROM skill_index WHERE id = old.skill_id),
           old.content;
END;

-- Schluesselwoerter pro Skill
CREATE TABLE IF NOT EXISTS skill_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL REFERENCES skill_index(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    source TEXT DEFAULT 'content',
    UNIQUE(skill_id, keyword)
);

-- ========================================================================
-- WIKIS (BACH Wiki-Artikel aus bach.db)
-- ========================================================================

-- Wiki-Metadaten (1 Zeile pro Wiki-Artikel)
CREATE TABLE IF NOT EXISTS wiki_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wiki_path TEXT UNIQUE NOT NULL,
    title TEXT,
    category TEXT,
    tags TEXT,
    content_hash TEXT,
    word_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    last_modified TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_db TEXT
);

-- Gechunkte Textabschnitte (N Zeilen pro Wiki)
CREATE TABLE IF NOT EXISTS wiki_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wiki_id INTEGER NOT NULL REFERENCES wiki_index(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    UNIQUE(wiki_id, chunk_index)
);

-- FTS5 Volltextindex ueber Wiki-Chunks
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    wiki_path,
    title,
    content,
    tokenize='unicode61'
);

-- Trigger: wiki_chunks -> wiki_fts sync
CREATE TRIGGER IF NOT EXISTS wiki_chunk_ai AFTER INSERT ON wiki_chunks BEGIN
    INSERT INTO wiki_fts(rowid, wiki_path, title, content)
    SELECT new.id,
           (SELECT wiki_path FROM wiki_index WHERE id = new.wiki_id),
           (SELECT title FROM wiki_index WHERE id = new.wiki_id),
           new.content;
END;

CREATE TRIGGER IF NOT EXISTS wiki_chunk_ad AFTER DELETE ON wiki_chunks BEGIN
    INSERT INTO wiki_fts(wiki_fts, rowid, wiki_path, title, content)
    SELECT 'delete', old.id,
           (SELECT wiki_path FROM wiki_index WHERE id = old.wiki_id),
           (SELECT title FROM wiki_index WHERE id = old.wiki_id),
           old.content;
END;

-- Schluesselwoerter pro Wiki
CREATE TABLE IF NOT EXISTS wiki_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wiki_id INTEGER NOT NULL REFERENCES wiki_index(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    source TEXT DEFAULT 'content',
    UNIQUE(wiki_id, keyword)
);

-- ========================================================================
-- DOCUMENTS (Ingested Dateien: PDF, DOCX, TXT, MD, HTML)
-- ========================================================================

-- Dokument-Metadaten (1 Zeile pro ingesteter Datei)
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    content_hash TEXT,
    language TEXT,
    word_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    page_count INTEGER DEFAULT 0,
    extraction_method TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_path TEXT,
    source_dir TEXT
);

-- Gechunkte Textabschnitte (N Zeilen pro Dokument)
CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    UNIQUE(doc_id, chunk_index)
);

-- FTS5 Volltextindex ueber Document-Chunks
CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
    filename,
    content,
    tokenize='unicode61'
);

-- Trigger: document_chunks -> document_fts sync
CREATE TRIGGER IF NOT EXISTS doc_chunk_ai AFTER INSERT ON document_chunks BEGIN
    INSERT INTO document_fts(rowid, filename, content)
    SELECT new.id,
           (SELECT filename FROM documents WHERE id = new.doc_id),
           new.content;
END;

CREATE TRIGGER IF NOT EXISTS doc_chunk_ad AFTER DELETE ON document_chunks BEGIN
    INSERT INTO document_fts(document_fts, rowid, filename, content)
    SELECT 'delete', old.id,
           (SELECT filename FROM documents WHERE id = old.doc_id),
           old.content;
END;

-- Schluesselwoerter pro Dokument
CREATE TABLE IF NOT EXISTS document_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    source TEXT DEFAULT 'content',
    UNIQUE(doc_id, keyword)
);

-- ========================================================================
-- SUMMARIES (LLM-Zusammenfassungen, quelluebergreifend)
-- ========================================================================

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    summary TEXT NOT NULL,
    keywords TEXT,
    domain TEXT,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id, chunk_index)
);

-- ========================================================================
-- DIGEST QUEUE (Processing Pipeline)
-- ========================================================================

CREATE TABLE IF NOT EXISTS digest_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    step TEXT DEFAULT 'summarize',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_msg TEXT,
    UNIQUE(source_type, source_id, step)
);

-- ========================================================================
-- META
-- ========================================================================

-- Schema-Version
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- ========================================================================
-- INDIZES
-- ========================================================================

-- Skills
CREATE INDEX IF NOT EXISTS idx_skill_type ON skill_index(skill_type);
CREATE INDEX IF NOT EXISTS idx_skill_category ON skill_index(category);
CREATE INDEX IF NOT EXISTS idx_skill_active ON skill_index(is_active);
CREATE INDEX IF NOT EXISTS idx_chunk_skill ON skill_chunks(skill_id);
CREATE INDEX IF NOT EXISTS idx_keyword_skill ON skill_keywords(skill_id);
CREATE INDEX IF NOT EXISTS idx_keyword_text ON skill_keywords(keyword);

-- Wikis
CREATE INDEX IF NOT EXISTS idx_wiki_category ON wiki_index(category);
CREATE INDEX IF NOT EXISTS idx_wiki_modified ON wiki_index(last_modified);
CREATE INDEX IF NOT EXISTS idx_wiki_chunk_wiki ON wiki_chunks(wiki_id);
CREATE INDEX IF NOT EXISTS idx_wiki_keyword_wiki ON wiki_keywords(wiki_id);
CREATE INDEX IF NOT EXISTS idx_wiki_keyword_text ON wiki_keywords(keyword);

-- Documents
CREATE INDEX IF NOT EXISTS idx_doc_type ON documents(file_type);
CREATE INDEX IF NOT EXISTS idx_doc_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_doc_chunk_doc ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_keyword_doc ON document_keywords(doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_keyword_text ON document_keywords(keyword);

-- Summaries
CREATE INDEX IF NOT EXISTS idx_summary_source ON summaries(source_type, source_id);

-- Queue
CREATE INDEX IF NOT EXISTS idx_queue_status ON digest_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_source ON digest_queue(source_type, source_id);
"""


def ensure_schema(db_path: Path) -> sqlite3.Connection:
    """Erstellt Schema falls noetig, gibt Connection zurueck."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
        (str(SCHEMA_VERSION),)
    )
    conn.commit()
    return conn


def get_schema_version(db_path: Path) -> int:
    """Liest Schema-Version aus DB, 0 wenn nicht vorhanden."""
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except Exception:
        return 0
