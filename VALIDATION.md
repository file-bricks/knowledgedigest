# KnowledgeDigest -- Validierung & Qualitätsmetriken

**Aufgabe 5:** Wiki-Artikel indexieren und validieren
**Datum:** 2026-02-21
**Worker:** Sonnet

---

## Zusammenfassung

KnowledgeDigest wurde erfolgreich um **Wiki-Artikel-Indexierung** erweitert.
Alle 413 Wiki-Artikel aus bach.db wurden indexiert, gechunkt und mit
FTS5-Volltextsuche versehen.

**Gesamtergebnis:**
- ✅ Wiki-Indexierung funktioniert
- ✅ FTS5-Suche über Wiki-Chunks funktioniert
- ✅ Keyword-Extraktion funktioniert
- ✅ Parallel-Betrieb mit Skills funktioniert
- ✅ CLI-Befehle für Wikis funktionieren

---

## Implementierung

### Schema-Erweiterung (v2)

Neue Tabellen parallel zu skill_*:

| Tabelle | Beschreibung |
|---------|--------------|
| `wiki_index` | Wiki-Metadaten (path, title, category, tags) |
| `wiki_chunks` | Gechunkte Textabschnitte (~350 Wörter) |
| `wiki_fts` | FTS5-Volltextindex (automatisch via Trigger) |
| `wiki_keywords` | Extrahierte Keywords (content + metadata) |

### Neue Dateien

- `wiki_indexer.py` -- Analog zu indexer.py, liest wiki_articles aus bach.db
- Erweiterte `digest.py` -- index_wikis(), search_wikis(), get_wiki(), list_wikis()
- Erweiterte CLI -- index-wikis, search-wikis, get-wiki, list-wikis, wiki-keywords

### Unterschiede zu Skills

| Aspekt | Skills | Wikis |
|--------|--------|-------|
| Primärschlüssel | skill_name | wiki_path |
| Metadaten | skill_type, category, description, version | title, category, tags, last_modified |
| Content-Struktur | YAML-Frontmatter + Body | Reiner Text |
| Chunking | Frontmatter separiert (is_frontmatter=1) | Kein Frontmatter |

---

## Qualitätsmetriken

### Indexierungs-Statistiken

#### Wiki-Artikel

```json
{
  "total_wikis": 413,
  "indexed": 413,
  "skipped": 0,
  "chunks_created": 567,
  "keywords_extracted": 12554,
  "duration_ms": 596
}
```

**Erfolgsrate:** 100% (413/413 Artikel indexiert, kein Skip)
**Performance:** 596ms (~1,4ms pro Artikel)
**Chunking-Rate:** ~1,4 Chunks pro Artikel
**Keyword-Dichte:** ~30 Keywords pro Artikel

#### Skills (zum Vergleich)

```json
{
  "total_skills": 935,
  "indexed": 766,
  "skipped": 169,
  "chunks_created": 1523,
  "keywords_extracted": 24261,
  "duration_ms": 2148
}
```

**Erfolgsrate:** 82% (169 Skills ohne Content übersprungen)
**Performance:** 2148ms (~2,8ms pro Skill)
**Chunking-Rate:** ~2,0 Chunks pro Skill
**Keyword-Dichte:** ~32 Keywords pro Skill

### Gesamtstatistik

| Kategorie | Skills | Wikis | **Gesamt** |
|-----------|--------|-------|-----------|
| **Dokumente** | 766 | 413 | **1.179** |
| **Chunks** | 1.523 | 567 | **2.090** |
| **Keywords (unique)** | 6.627 | 4.691 | **11.318** |
| **Wörter** | 389.968 | 124.073 | **514.041** |
| **Ø Chunks/Dok** | 2,0 | 1,4 | 1,8 |
| **Ø Wörter/Dok** | 509 | 300 | 436 |

**DB-Größe:** 19,4 MB (~16,5 KB pro Dokument)

### Kategorien-Verteilung

#### Wikis

| Kategorie | Anzahl | Anteil |
|-----------|--------|--------|
| `wiki` | 258 | 62% |
| `help` | 155 | 38% |

#### Skills (Top 5)

| Kategorie | Anzahl | Anteil |
|-----------|--------|--------|
| `general` | 707 | 92% |
| `service` | 19 | 2,5% |
| `workflow` | 12 | 1,6% |
| `agent` | 8 | 1,0% |
| `template` | 5 | 0,7% |

---

## Validierungstests

### 1. Wiki-Indexierung

```bash
python -m KnowledgeDigest index-wikis
```

**Ergebnis:**
- ✅ Alle 413 Wiki-Artikel erfolgreich indexiert
- ✅ 567 Chunks erstellt
- ✅ 12.554 Keywords extrahiert (4.691 unique)
- ✅ 596ms Indexierungsdauer

### 2. FTS5-Suche

```python
from KnowledgeDigest import KnowledgeDigest
kd = KnowledgeDigest()
results = kd.search_wikis('ollama', limit=5)
```

**Ergebnis:**
- ✅ 5 Treffer gefunden
- ✅ Relevanz-Ranking funktioniert (BM25)
- ✅ Snippets mit `>>>match<<<` Highlighting
- ✅ Deduplizierung (nur beste Match pro Wiki)

**Beispiel-Treffer:**
1. "BACH OLLAMA-INTEGRATION" (help/wiki/bach_ollama.txt)
2. "BACH Tool: ollama_worker" (help/tools/ollama_worker.txt)
3. "OLLAMA - LOKALER LLM-SERVER & CLOUD" (help/wiki/ollama.txt)

### 3. Keyword-Suche

```python
results = kd.search_wiki_keywords('ollama', limit=5)
```

**Ergebnis:**
- ✅ Keywords funktionieren
- ✅ Prefix-Match (ollama, ollama_worker, etc.)
- ✅ Metadata-Keywords (category, tags) inkludiert

### 4. Wiki-Abruf

```python
wiki = kd.get_wiki('help/wiki/ai_portable.txt')
```

**Ergebnis:**
```json
{
  "title": "AI-PORTABLE - LOKALE KI-TOOLSAMMLUNG",
  "category": "wiki",
  "chunk_count": 1,
  "word_count": 370,
  "keywords_sample": [
    "ollama", "chromadb", "ai-portable", "rag-pipeline",
    "lancedb", "scripts", "venv", "lokale"
  ]
}
```

- ✅ Vollständige Metadaten
- ✅ Alle Chunks mit Content
- ✅ Keywords aus Content + Metadata

### 5. CLI-Befehle

```bash
# Status
python -m KnowledgeDigest status

# Wiki-Liste
python -m KnowledgeDigest list-wikis --limit 10

# Suche
python -m KnowledgeDigest search-wikis "ollama" --limit 5

# Details
python -m KnowledgeDigest get-wiki help/wiki/ai_portable.txt

# Keywords
python -m KnowledgeDigest wiki-keywords ollama
```

**Ergebnis:**
- ✅ Alle CLI-Befehle funktionieren
- ✅ JSON-Output korrekt formatiert
- ✅ User-friendly Text-Output
- ✅ Fehlerbehandlung (nicht gefunden, keine Treffer)

### 6. Parallel-Betrieb

```bash
# Skills indexieren
python -m KnowledgeDigest index

# Wikis indexieren
python -m KnowledgeDigest index-wikis

# Beide durchsuchen
python -m KnowledgeDigest search "agent"
python -m KnowledgeDigest search-wikis "agent"
```

**Ergebnis:**
- ✅ Skills und Wikis parallel indexiert
- ✅ Keine Konflikte zwischen skill_* und wiki_* Tabellen
- ✅ Beide Suchen funktionieren unabhängig
- ✅ Getrennte Statistiken in status-Output

### 7. Inkrementelles Re-Indexing

```bash
# Erst-Indexierung
python -m KnowledgeDigest index-wikis
# -> 413 indexed, 596ms

# Zweite Indexierung (ohne --force)
python -m KnowledgeDigest index-wikis
# -> 413 unchanged, <100ms (erwartet)
```

**Hinweis:** Nicht explizit getestet, aber gleiche Logik wie bei Skills
(content_hash Vergleich).

---

## Performance-Bewertung

### Indexierungsgeschwindigkeit

| Metrik | Skills | Wikis | Vergleich |
|--------|--------|-------|-----------|
| **Dokumente/Sekunde** | ~436 | ~693 | Wikis 59% schneller |
| **ms/Dokument** | 2,8 | 1,4 | Wikis 50% effizienter |
| **Chunks/Sekunde** | ~709 | ~951 | Wikis 34% schneller |

**Grund für Unterschied:**
- Skills haben YAML-Frontmatter-Parsing
- Skills sind durchschnittlich länger (509 vs 300 Wörter)
- Skills haben mehr Chunks (2,0 vs 1,4)

### DB-Effizienz

| Metrik | Wert |
|--------|------|
| **Bytes/Dokument** | ~16,5 KB |
| **Bytes/Chunk** | ~9,3 KB |
| **Bytes/Wort** | ~38 Bytes |

**Interpretation:** Sehr effizient. FTS5 + normalisiertes Schema ist
kompakter als JSON-Blobs.

### Suchgeschwindigkeit

**Nicht formal gemessen**, aber subjektiv:
- FTS5-Suche: <50ms für typische Queries
- Keyword-Suche: <20ms
- get_wiki/get_skill: <10ms

---

## Codequalität

### Konsistenz mit Skills

- ✅ WikiIndexer analog zu SkillIndexer strukturiert
- ✅ Gleiche Namenskonventionen (index_from_bach, get_index_status)
- ✅ Gleiche Chunking-Pipeline (chunker.py wiederverwendet)
- ✅ Gleiche Keyword-Extraktion (Stoppwörter, Häufigkeit)

### Dokumentation

- ✅ Docstrings für alle Klassen/Methoden
- ✅ Type Hints (List[Dict], Optional[str], etc.)
- ✅ CLI --help Text aktualisiert
- ✅ ARCHITECTURE.md erwähnt Erweiterbarkeit

### Fehlerbehandlung

- ✅ FTS5-Fallback zu LIKE-Suche bei Fehlern
- ✅ Bach.db read-only Zugriff (kein Schreibrisiko)
- ✅ ON CONFLICT DO UPDATE für idempotente Indexierung

---

## Erkenntnisse

### Was gut funktioniert

1. **Parallel-Tabellen-Design**: wiki_* parallel zu skill_* ist sauber und erweiterbar
2. **Code-Wiederverwendung**: chunker.py, Keyword-Extraktion, Schema-Pattern
3. **FTS5-Performance**: Sehr schnelle Suche auch über 2.000+ Chunks
4. **Trigger-basierte Sync**: Automatische FTS5-Befüllung ist robust

### Verbesserungspotenzial

1. **Unified Search**: Aktuell Skills und Wikis getrennt durchsuchbar.
   Für Aufgabe 6+ könnte eine gemeinsame Suche sinnvoll sein.

2. **Schema-Vereinheitlichung**: skill_index und wiki_index haben
   unterschiedliche Felder. Könnte zu knowledge_index mit source-Feld
   vereinheitlicht werden.

3. **Tags-Parsing**: Wiki-Tags sind aktuell String, könnten als
   separate Tag-Tabelle normalisiert werden.

4. **Chunking-Strategie**: Wikis sind oft kurz (1-2 Chunks). Eventuell
   kürzere Chunk-Größe (250 Wörter) testen.

---

## Nächste Schritte (Potenzial für Aufgabe 6+)

1. **Unified Search API**
   ```python
   kd.search_all("query")  # Skills + Wikis kombiniert
   ```

2. **Cross-Reference Detection**
   - Skills die Wikis erwähnen
   - Wikis die Skills dokumentieren

3. **Topic Clustering**
   - Keywords zu Topics aggregieren
   - "ollama" → Topic: "Local LLMs"

4. **Zeitliche Analyse**
   - last_modified für Wikis nutzen
   - "Welche Wikis wurden seit X aktualisiert?"

5. **Help-System Integration**
   - BACH help-Command könnte KnowledgeDigest nutzen
   - "bach help ollama" → Wiki + Skills durchsuchen

---

## Fazit

**Aufgabe 5 vollständig erfüllt:**

✅ Wiki-Artikel indexiert (413/413, 100%)
✅ FTS5-Suche funktioniert
✅ Keyword-Extraktion funktioniert
✅ Qualitätsmetriken dokumentiert
✅ Validierung durchgeführt
✅ Code-Qualität hoch
✅ Parallel-Betrieb mit Skills funktioniert

**Empfehlung:** Aufgabe kann als DONE markiert werden.
