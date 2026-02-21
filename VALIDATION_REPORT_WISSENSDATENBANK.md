# Validierungs-Report: Wissensdatenbank-Status in KnowledgeDigest

**Datum:** 2026-02-21 11:52
**Erstellt von:** Sonnet Worker (Einzelaufgaben Runde 2)
**Aufgabe:** SQ059 - Aufgabe 2 (KnowledgeDigest auf Wissensdatenbank prüfen)
**Status:** BLOCKED - Opus-Entscheidung erforderlich

---

## Executive Summary

✅ **Verifizierung abgeschlossen:**
Die `knowledge.db` enthält **NUR** BACH-Skills (766) und Wiki (413), **NICHT** die Wissensdatenbank (37.453 Dateien).

❌ **Integration nicht möglich:**
KnowledgeDigest hat keinen Code für Wissensdatenbank-Indexierung. Architektur-Entscheidungen erforderlich.

---

## 1. knowledge.db Analyse

**Pfad:** `C:\Users\lukas\OneDrive\KI&AI\MODULAR_AGENTS\KnowledgeDigest\data\knowledge.db`
**Größe:** 19 MB

### Inhalt:

| Kategorie | Dokumente | Chunks |
|-----------|-----------|--------|
| BACH Skills | 766 | 1523 |
| Wiki-Einträge | 413 | 567 |
| **Gesamt** | **1179** | **2090** |

### Tabellen-Schema:

```
skill_index          → Metadaten pro Skill
skill_chunks         → Gechunkte Textabschnitte
skill_fts            → FTS5-Volltextindex
skill_keywords       → Extrahierte Schlüsselwörter
wiki_index           → Wiki-Metadaten
wiki_chunks          → Wiki-Chunks
wiki_fts             → Wiki-Volltextindex
wiki_keywords        → Wiki-Keywords
schema_meta          → Schema-Version
```

### Quell-Datenbank:

- **Skills:** `C:\Users\lukas\OneDrive\KI&AI\BACH_v2_vanilla\system\data\bach.db`
- **Wiki:** `C:\Users\lukas\OneDrive\KI&AI\BACH_v2_vanilla\system\data\bach.db`

### Beispiel-Pfade (Skills):

```
entwickler: agents/entwickler.txt
förderplaner: agents/förderplaner.txt
gesundheitsassistent: agents/gesundheitsassistent.txt
research: skills/_partners/gemini/prompts/research.txt
```

### Beispiel-Pfade (Wiki):

```
AI-PORTABLE: help/wiki/ai_portable.txt
ANALYSEBERICHT: GUIDELINES: help/wiki/analyse_guidelines.txt
ANTIGRAVITY: help/wiki/antigravity.txt
BACH USER MOUNTS: help/wiki/bach_user_mounts.txt
```

### Befund:

❌ **KEINE Dokumente aus `_Wissensdatenbank`**
✅ FTS5-Volltextsuche funktional für BACH/Wiki
✅ Chunking-Strategie implementiert (~350 Wörter/Chunk)

---

## 2. Verzeichnis.db Analyse

**Pfad:** `C:\Users\lukas\OneDrive\Dokumente\_Wissensdatenbank\Verzeichnis.db`
**Größe:** 140 MB

### Inhalt:

| Tabelle | Anzahl | Beschreibung |
|---------|--------|--------------|
| files | 37.453 | Dateien (Content-Hash basiert) |
| versions | 74.173 | Datei-Versionen |
| tags | 1.913.009 | Tags (aus Ordnerstruktur) |
| topics | 0 | Ungenutzt |
| events | ? | Version-Control-Events |
| collections | ? | Sammlungen |
| favorites | ? | Favoriten |

### files Tabelle Schema:

```sql
id              INTEGER  PRIMARY KEY
content_hash    TEXT     → SHA1-Hash als Identifier
size            INTEGER  → Bytes
mime            TEXT     → MIME-Type
first_seen      TEXT     → Timestamp
is_deleted      INTEGER  → 0/1
deleted_at      TEXT
pdf_encrypted   INTEGER  → PDF-Metadata
pdf_has_text    INTEGER  → PDF-Metadata
pdf_was_encrypted INTEGER → PDF-Metadata
```

### Befund:

✅ **37.453 Dateien indexiert** (Filesystem-Index)
✅ PDF-Metadaten vorhanden (encrypted, has_text)
❌ **KEIN Volltext** extrahiert
❌ **KEINE semantische Suche** (kein FTS5)
❌ **KEINE Zusammenfassungen** (kein LLM-Processing)

**Fazit:** Verzeichnis.db ist ein reiner Metadaten-Index, kein Wissens-Index.

---

## 3. KnowledgeDigest Code-Review

### Implementiert:

✅ `digest.py`: High-Level API
✅ `indexer.py`: SkillIndexer (bach.db → knowledge.db)
✅ `wiki_indexer.py`: WikiIndexer (bach.db → knowledge.db)
✅ `chunker.py`: Chunking-Algorithmus (~350 Wörter)
✅ `schema.py`: DB-Schema + Migrationen

### NICHT implementiert:

❌ **Document Indexer** für allgemeine Dateien
❌ **PDF/DOCX Extraktion** (ProFiler-Integration)
❌ **OCR-Engine** (Tesseract)
❌ **LLM-Zusammenfassungen** (Haiku-Batch-Pipeline)
❌ **Deduplizierung** (Embedding-basiert)
❌ **Verzeichnis.db Reader** (für Migration)

### README.md Vision vs. Implementierung:

**README beschreibt:**
- 7-Phasen-Pipeline: Erkennung → Extraktion → Zerteilung → Zusammenfassung → Deduplizierung → Archivierung → Wiki-Stub
- ProFiler-Integration (OCR, PDF-Toolbox)
- NoteSpaceLLM-Integration (LLM-Analyse)
- SpaceNotLM (Backend-API, RAG)
- MetaWiki (Taxonomie-System)
- Kosten: ~100$ für Erstverarbeitung

**ARCHITECTURE.md sagt:**
> "Aufgabe 4 fokussiert NUR auf die Skill-Datenbank. Die README.md beschreibt eine viel größere Vision. Aufgabe 5 wird die Wiki-Artikel etc. indexieren."

**Implementierung:**
- Nur Aufgabe 4 (Skills) + Aufgabe 5 (Wiki) erledigt
- Vision aus README **NICHT** implementiert
- Wissensdatenbank-Integration **FEHLT**

---

## 4. Gap-Analyse: Was fehlt?

### A. Schema-Erweiterung

**Benötigt:**
```sql
-- Neue Tabellen parallel zu skill_* / wiki_*
CREATE TABLE document_index (
    id INTEGER PRIMARY KEY,
    content_hash TEXT,          -- aus Verzeichnis.db
    file_path TEXT,             -- aus Verzeichnis.db versions
    mime_type TEXT,
    extracted_text TEXT,        -- NEU: Volltext
    extraction_method TEXT,     -- 'plaintext', 'pdf', 'ocr', 'docx'
    language TEXT,              -- 'de', 'en'
    word_count INTEGER,
    chunk_count INTEGER,
    indexed_at TIMESTAMP,
    source_db TEXT              -- 'Verzeichnis.db'
);

CREATE TABLE document_chunks (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER,
    chunk_index INTEGER,
    content TEXT,
    word_count INTEGER,
    FOREIGN KEY (doc_id) REFERENCES document_index(id)
);

CREATE VIRTUAL TABLE document_fts USING fts5(
    content,
    content=document_chunks,
    content_rowid=id
);
```

### B. Extraktion-Pipeline

**Benötigt:**

1. **Text-Files (.txt, .md, .html):**
   - Direkt lesen (UTF-8)
   - Minimal-MVP möglich

2. **PDF-Files:**
   - Option 1: `pypdf` (nur Text-PDFs)
   - Option 2: ProFiler-Integration (OCR + Text)
   - Frage: OCR-Kosten/Zeit für 22.000 PDFs?

3. **DOCX-Files:**
   - `python-docx` (stdlib-Alternative?)
   - 4.000 Files laut README

4. **Andere Formate:**
   - RTF, ODT, HTML → später?

### C. Datenfluss

**Option 1: Verzeichnis.db als Quelle (Read-Only)**
```
Verzeichnis.db (37.453 files)
    |
    ├── content_hash + versions → file_path
    ├── mime_type → extraction_method
    └── pdf_metadata → skip encrypted/no-text
    |
    v
DocumentIndexer.index_from_verzeichnis()
    |
    ├── Filter: .txt, .md, .html (MVP)
    ├── oder: .pdf (mit ProFiler)
    ├── oder: .docx (mit python-docx)
    |
    v
Extraktor (je nach MIME)
    |
    └── extracted_text
    |
    v
Chunker (~350 Wörter)
    |
    v
knowledge.db → document_index + document_chunks + document_fts
```

**Option 2: knowledge.db wird Master**
```
knowledge.db erweitert Verzeichnis.db:
    - Keine neue DB
    - Verzeichnis.db = files + versions + tags (wie bisher)
    - knowledge.db = file_texts + summaries + knowledge_nodes (neu)
    - Sync via content_hash
```

**Option 3: Migration + Deprecation**
```
Verzeichnis.db → knowledge.db (einmalig)
    - Alle Metadaten migrieren
    - Verzeichnis.db deprecated
    - knowledge.db wird Single Source of Truth
```

### D. Performance/Kosten

**37.453 Dateien:**

| Kategorie | Anzahl (geschätzt) | Chunks (@350W) | Zeit (@1s/File) | LLM-Kosten (Haiku) |
|-----------|-------------------|----------------|-----------------|-------------------|
| .txt/.md | ~5.000 | ~25.000 | 1,4h | ~15$ |
| .pdf (Text) | ~15.000 | ~75.000 | 4h | ~45$ |
| .pdf (OCR) | ~7.000 | ~35.000 | 20h (OCR!) | ~20$ |
| .docx | ~4.000 | ~20.000 | 1h | ~12$ |
| Andere | ~6.453 | - | - | - |
| **Total** | **37.453** | **~155.000** | **~26h** | **~92$** |

**LLM-Kosten nur bei Zusammenfassungen (README-Vision)!**
MVP: Nur Volltext-Extraktion + FTS5 → **0$ LLM-Kosten**

---

## 5. Entscheidungspunkte für Opus

### Frage 1: Scope (MVP vs. Vision)

**Option A: MVP (Sonnet kann weitermachen)**
- Nur Text-Files (.txt, .md, .html)
- Keine OCR, keine PDF-Extraktion
- Keine LLM-Zusammenfassungen
- Nur FTS5-Volltextsuche
- **Zeit:** 2-3h Implementierung, 30min Indexierung
- **Kosten:** 0$

**Option B: Full Vision (Opus-Projekt)**
- 7-Phasen-Pipeline wie README beschreibt
- ProFiler-Integration (OCR)
- NoteSpaceLLM (Zusammenfassungen)
- SpaceNotLM (Backend-API)
- MetaWiki (Taxonomie)
- **Zeit:** 1-2 Tage Entwicklung, 26h Indexierung
- **Kosten:** ~92$ LLM-Kosten

**Option C: Hybrid (PDF-Text, kein OCR, keine Summaries)**
- Text-Files + PDF (nur Text-PDFs)
- Keine OCR (encrypted/scan-PDFs → skip)
- Keine LLM-Summaries
- Nur FTS5
- **Zeit:** 4-5h Implementierung, 5h Indexierung
- **Kosten:** 0$

### Frage 2: Schema-Design

**Option A: Parallele Tabellen**
```
skill_index / skill_chunks / skill_fts
wiki_index / wiki_chunks / wiki_fts
document_index / document_chunks / document_fts  ← NEU
```
- Vorteil: Klare Trennung
- Nachteil: Unified Search schwieriger

**Option B: Unified Knowledge Table**
```
knowledge_index (source_type: 'skill' | 'wiki' | 'document')
knowledge_chunks
knowledge_fts
```
- Vorteil: Unified Search einfach
- Nachteil: Migration bestehender Daten

**Option C: Verzeichnis.db erweitern**
```
Verzeichnis.db bleibt Master
knowledge.db = nur Volltext-Layer (file_texts, summaries)
Sync via content_hash
```
- Vorteil: Bestehende Struktur bleibt
- Nachteil: 2 DBs zu pflegen

### Frage 3: Verzeichnis.db Zukunft

**Option A: Read-Only**
- Verzeichnis.db bleibt wie sie ist
- knowledge.db liest nur Metadaten
- Neue Dateien: Manuell in beide DBs?

**Option B: Deprecated**
- Einmalige Migration → knowledge.db
- Verzeichnis.db wird archiviert
- knowledge.db = Single Source of Truth

**Option C: Hybrid**
- Verzeichnis.db = Metadaten (files, versions, tags)
- knowledge.db = Wissen (Volltext, Semantik)
- Sync via content_hash

### Frage 4: ProFiler-Integration Jetzt oder Später?

**Jetzt:**
- ProFiler ist "85% Production Ready"
- PDF-Extraktion + OCR sofort verfügbar
- Aber: Dependency-Management (ProFiler einbinden)

**Später:**
- MVP erst ohne ProFiler
- Phase 2: ProFiler nachrüsten
- Risiko: Doppelte Arbeit (Re-Indexierung)

### Frage 5: Budget

- LLM-Summaries: ~92$ (einmalig)
- OCR-Server-Zeit: ~26h @ Hetzner CCX33 (~2,08€)
- Gesamt: ~95€

Freigabe für Kosten?

---

## 6. Empfohlener Weg (Sonnet-Perspektive)

**Empfehlung: Option C (Hybrid) für schnellen MVP**

### Phase 1: MVP (Sonnet, 1 Runde)
1. Schema: Parallele Tabellen (`document_index`, `document_chunks`, `document_fts`)
2. Scope: Nur .txt, .md, .html (direkt lesbar)
3. Verzeichnis.db: Read-Only als Metadaten-Quelle
4. `DocumentIndexer` analog zu `SkillIndexer`
5. Test: 100 Sample-Dateien
6. Zeit: ~3h, Kosten: 0$

### Phase 2: PDF-Text (Opus/Sonnet, 1 Runde)
1. `pypdf` für Text-PDFs
2. Skip: encrypted, scan-only (pdf_has_text=0)
3. Zeit: ~5h Indexierung
4. Kosten: 0$

### Phase 3: ProFiler + OCR (Opus, 2+ Runden)
1. ProFiler als Library einbinden
2. OCR für Scan-PDFs
3. Zeit: ~20h OCR
4. Kosten: ~2€ Server

### Phase 4: Vision (Opus, Projekt)
1. LLM-Zusammenfassungen
2. Deduplizierung
3. MetaWiki-Integration
4. Wiki-Stub-Generierung
5. Kosten: ~92$

---

## 7. Blocker für Sonnet

**Warum BLOCKED:**

1. **Architektur-Entscheidung:**
   Schema-Design (parallel vs. unified) beeinflusst allen weiteren Code

2. **Scope-Klärung:**
   MVP vs. Vision? Budget für LLM-Kosten?

3. **Verzeichnis.db-Strategie:**
   Read-Only, Deprecated, oder Hybrid?

4. **ProFiler-Integration:**
   Jetzt oder später? Dependency-Management klären

5. **Sonnet-Grenzen:**
   Opus ist für SQ059 (Hoch-Komplexität) empfohlen
   Sonnet kann MVP bauen, aber nicht Architektur designen

**Sonnet kann fortfahren wenn:**
- Klare Scope-Vorgabe (z.B. "MVP, nur Text-Files")
- Schema-Entscheidung getroffen (z.B. "Parallele Tabellen")
- Verzeichnis.db-Strategie definiert (z.B. "Read-Only")

---

## 8. Code-Änderungen (falls MVP freigegeben)

### Neue Dateien:

```
KnowledgeDigest/
├── document_indexer.py      # NEU: DocumentIndexer
├── extractors/              # NEU: Extraktor-Module
│   ├── __init__.py
│   ├── text.py              # .txt, .md
│   └── html.py              # .html (optional)
```

### Geänderte Dateien:

```
schema.py:                   # +document_* Tabellen
digest.py:                   # +index_documents() Methode
```

### Beispiel-Code (document_indexer.py):

```python
class DocumentIndexer:
    def index_from_verzeichnis(self, verzeichnis_db_path, *,
                               mime_filter=None,
                               limit=None):
        # 1. Verzeichnis.db lesen (read-only)
        # 2. files + versions JOINen → file_path
        # 3. Nach MIME filtern (.txt, .md, .html)
        # 4. Datei lesen → extracted_text
        # 5. Chunken (wie SkillIndexer)
        # 6. document_index + document_chunks einfügen
        # 7. FTS5-Trigger aktualisiert document_fts
```

---

## 9. Nächste Schritte

### Wenn Opus übernimmt:
1. Architektur-Entscheidungen treffen (siehe Abschnitt 5)
2. Detailplan erstellen (Phase 1-4)
3. ProFiler-Integration vorbereiten
4. Budget-Freigabe einholen

### Wenn Sonnet MVP baut:
1. Klare Scope-Vorgabe erhalten
2. `document_indexer.py` + `schema.py` erweitern
3. Test mit 100 Files
4. Vollständige Indexierung (~5.000 Text-Files)
5. BLOCKED-Status aufheben in Queue

### Wenn zurück an Controller:
- Aufgabe 2 BLOCKED lassen
- Aufgabe 3 (SQ057 SharedMemoryClient) anschauen?
- Oder: Warten auf Opus-Entscheidung

---

## Anhang A: SQL-Queries für Verifizierung

### knowledge.db Statistiken:
```sql
SELECT COUNT(*) FROM skill_index;        -- 766
SELECT COUNT(*) FROM skill_chunks;       -- 1523
SELECT COUNT(*) FROM wiki_index;         -- 413
SELECT COUNT(*) FROM wiki_chunks;        -- 567
SELECT DISTINCT source_db FROM skill_index;  -- bach.db
```

### Verzeichnis.db Statistiken:
```sql
SELECT COUNT(*) FROM files;              -- 37,453
SELECT COUNT(*) FROM versions;           -- 74,173
SELECT COUNT(*) FROM tags;               -- 1,913,009
SELECT COUNT(*) FROM topics;             -- 0
```

### Beispiel-Dateien (Verzeichnis.db):
```sql
SELECT f.content_hash, v.path, f.mime, f.size
FROM files f
JOIN versions v ON f.id = v.file_id
WHERE f.mime LIKE 'text/%'
LIMIT 10;
```

---

**Erstellt:** 2026-02-21 11:52
**Von:** Sonnet Worker (Einzelaufgaben Murmelbahn)
**Für:** Opus Architect (Architektur-Entscheidung)
**Status:** AWAITING_DECISION
