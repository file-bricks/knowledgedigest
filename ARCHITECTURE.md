# KnowledgeDigest -- Architektur (v0.1.0)

## Abgrenzung: Aufgabe 4 vs. Vision

Aufgabe 4 fokussiert NUR auf die Skill-Datenbank:
- BACH-Skills (935 Eintraege, 766 mit Content) indexieren und durchsuchbar machen
- Eigene SQLite-DB (knowledge.db), NICHT bach.db modifizieren
- FTS5-basierte Volltextsuche ueber gechunkten Content
- Keyword-Extraktion fuer semantische Navigation

Die README.md beschreibt eine viel groessere Vision:
- 7-Phasen-Pipeline (Erkennung bis Wiki-Stub)
- ProFiler-Integration, NoteSpaceLLM, SpaceNotLM, MetaWiki
- ~37.000 Dateien aus der Wissensdatenbank
- LLM-basierte Zusammenfassungen (~100$ Kosten)

Aufgabe 5 wird die Wiki-Artikel etc. indexieren (baut auf dieser Grundstruktur auf).

## Entscheidungen

### Eigene DB statt bach.db erweitern
- bach.db gehoert BACH (36 MB, 935 Skills, 413 Wiki-Artikel)
- KnowledgeDigest ist ein externes Modul -- darf bach.db nicht modifizieren
- Liest bach.db read-only (`file:...?mode=ro`)
- Speichert alles in eigener knowledge.db unter data/
- Vorteil: Unabhaengig von BACH-Versionen, kein Risiko fuer BACH-Daten

### Normalisiertes Schema statt flache Tabelle
Handoff-Vorgabe war eine flache skill_knowledge Tabelle.
Implementiert: Normalisiertes 4-Tabellen-Schema:

| Tabelle | Rolle |
|---------|-------|
| skill_index | Metadaten pro Skill (1:1 mit BACH skills) |
| skill_chunks | Gechunkte Textabschnitte (1:N pro Skill) |
| skill_fts | FTS5-Volltextindex ueber einzelne Chunks |
| skill_keywords | Extrahierte Schluesselwoerter (1:N pro Skill) |

Begruendung: FTS5 ueber einzelne Chunks ist performanter als ueber
JSON-Blobs. Ermoeglicht granulare Snippet-Erzeugung und Relevanz-Ranking
auf Chunk-Ebene.

### Chunking-Strategie
- Target: ~350 Woerter pro Chunk (~400 Token)
- YAML-Frontmatter wird als eigener Chunk extrahiert
- Splitting an Absatz- und Satzgrenzen (nicht mitten im Satz)
- Zu kleine letzte Chunks (<50 Woerter) werden angehaengt
- Optionaler Overlap (Default: 0, konfigurierbar)

### FTS5 statt reine Keyword-Suche
- FTS5 bietet Ranking (BM25), Snippets, Prefix-Suche
- Automatische Synchronisation via SQLite-Trigger
- LIKE-Fallback wenn FTS5 fehlschlaegt
- Tokenizer: unicode61 (gut fuer DE/EN gemischt)

## Modul-Struktur

```
KnowledgeDigest/
├── __init__.py          # from .digest import KnowledgeDigest
├── __main__.py          # python -m KnowledgeDigest
├── digest.py            # Haupt-Klasse (High-Level API)
├── indexer.py           # SkillIndexer (bach.db -> knowledge.db)
├── chunker.py           # Chunking-Algorithmus
├── schema.py            # DB-Schema + Migration
├── requirements.txt     # Nur stdlib
├── ARCHITECTURE.md      # Dieses Dokument
├── README.md            # Konzept-Dokument (groessere Vision)
└── data/
    ├── .gitkeep
    └── knowledge.db     # Wird bei index_skills() erstellt
```

## Datenfluss

```
bach.db (read-only)
    |
    v
SkillIndexer.index_from_bach()
    |
    ├── Skills lesen (935 rows)
    ├── Content pruefen (766 mit Content, 169 ohne -> skip)
    ├── Content-Hash vergleichen (unveraenderte -> skip)
    |
    v
Chunker.chunk_text()
    |
    ├── Frontmatter separieren
    ├── Body in Segmente splitten (Satz/Absatz-Grenzen)
    └── Segmente zu ~350-Wort-Chunks aggregieren
    |
    v
knowledge.db
    |
    ├── skill_index (Metadaten)
    ├── skill_chunks (Chunk-Content)
    ├── skill_fts (FTS5, via Trigger)
    └── skill_keywords (extrahierte Keywords)
```

## API (digest.py)

| Methode | Beschreibung |
|---------|-------------|
| `index_skills(bach_db_path)` | Skills aus bach.db indexieren |
| `search(query)` | FTS5-Suche ueber Chunks |
| `search_keywords(keyword)` | Keyword-basierte Suche |
| `get_skill(name)` | Einzelnen Skill mit Chunks abrufen |
| `list_skills()` | Alle indexierten Skills auflisten |
| `get_status()` | Index-Statistiken |

## CLI

```bash
python -m KnowledgeDigest index [--bach-db PATH] [--force]
python -m KnowledgeDigest search "query" [--type TYPE] [--limit N]
python -m KnowledgeDigest get skill_name
python -m KnowledgeDigest status
python -m KnowledgeDigest keywords KEYWORD
python -m KnowledgeDigest list [--type TYPE] [--category CAT]
```

## Erweiterbarkeit (Aufgabe 5+)

Das Schema ist so designed, dass Aufgabe 5 (Wiki-Artikel indexieren)
einfach weitere Tabellen hinzufuegen kann:
- wiki_index, wiki_chunks, wiki_fts (parallel zu skill_*)
- Oder: skill_index erweitern zu knowledge_index mit source-Feld
- schema_meta ermoeglicht Schema-Migrationen

## Technische Constraints
- Nur Python stdlib (sqlite3, re, pathlib, hashlib, dataclasses)
- PYTHONIOENCODING=utf-8 bei allen Aufrufen
- Windows-kompatibel (Pfade, Encoding)
- bach.db wird NIEMALS modifiziert (read-only Zugriff)
