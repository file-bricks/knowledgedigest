# KnowledgeDigest → BACH Integration Gap-Analyse

**Datum:** 2026-02-21 12:20
**Erstellt von:** Sonnet Worker (Einzelaufgaben, Vorbereitungsarbeit)
**Aufgabe:** SQ059 - Aufgabe 4 (KnowledgeDigest BACH-Integration)
**Status:** VORBEREITUNG - Für Opus-Übernahme
**Abhängigkeit:** Aufgabe 2 (BLOCKED - Wissensdatenbank-Indexierung)

---

## Executive Summary

✅ **KnowledgeDigest** existiert und funktioniert (Skills + Wiki indexiert)
✅ **BACH unified_search.py** existiert (SQ047 - search_index + search_fts)
❌ **KEINE Integration** zwischen KnowledgeDigest und BACH

**Gap:** KnowledgeDigest ist standalone. Agenten können nicht darauf zugreifen.

**Aufgabe:** Connector schreiben der KnowledgeDigest in BACH einbindet (unified_search nutzen).

---

## 1. Aktueller Stand

### A. KnowledgeDigest (Modul)

**Pfad:** `C:\Users\lukas\OneDrive\KI&AI\MODULAR_AGENTS\KnowledgeDigest\`
**Version:** 0.1.0 (Aufgabe 4 + 5 aus BACH_Dev/MASTERPLAN)
**Status:** Basis-Implementation (Skills + Wiki)

**Inhalt (knowledge.db):**
- 766 BACH Skills (1523 Chunks)
- 413 Wiki-Einträge (567 Chunks)
- **Gesamt: 1179 Dokumente, 2090 Chunks**
- ❌ Wissensdatenbank (37.453 Dateien) NICHT indexiert (siehe Aufgabe 2)

**Tabellen:**
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

**API (digest.py):**
```python
# KnowledgeDigest Klasse
kd = KnowledgeDigest()

# Indexierung
kd.index_skills(bach_db_path)       # Skills aus bach.db
# (index_wiki wird intern aufgerufen)

# Suche
results = kd.search(query, limit=20, skill_type=None, category=None)
keywords = kd.search_keywords(keyword)
skill = kd.get_skill(skill_name)
skills = kd.list_skills(skill_type=None, category=None)

# Status
stats = kd.get_status()
```

**Architektur:**
- Eigene DB: `data/knowledge.db` (19 MB)
- Read-Only Zugriff auf bach.db
- FTS5-basierte Volltext-Suche
- Chunking: ~350 Wörter/Chunk
- Nur stdlib (kein LLM, keine OCR)

### B. BACH unified_search.py

**Pfad:** `C:\Users\lukas\OneDrive\KI&AI\BACH_v2_vanilla\system\tools\unified_search.py`
**Version:** 1.0.0
**Author:** Claude Opus 4.6
**Created:** 2026-02-20
**Implements:** SQ064 (Semantische Suche) + SQ047 (Wissensindexierung)

**Inhalt (bach.db):**
```sql
search_index (table)  -- unified metadata + content from all sources
  - source: 'document', 'wiki', 'memory_working', 'memory_fact', 'memory_lesson', 'file'
  - source_id, source_path, title, content
  - category, content_hash (SHA256), word_count, file_size

search_fts (FTS5)      -- full-text index synced via triggers
  - title, content

search_tags (table)    -- tags per indexed item (ProFiler pattern)
  - search_id, tag
```

**API (UnifiedSearch Klasse):**
```python
# unified_search.py
engine = UnifiedSearch(db_path)

# Suche
results = engine.search(query, limit=20, sources=None)

# Indexierung
engine.index_all()                   # Alle Quellen
engine.index_wiki()                  # Wiki-Artikel
engine.index_memory()                # Memory (working, facts, lessons)
engine.index_documents()             # help/ Dateien
engine.index_directory(path)         # Beliebiges Verzeichnis

# Status
stats = engine.get_status()
tags = engine.get_all_tags()
dupes = engine.find_duplicates()
```

**Quellen (aktuell indexiert):**
- ✅ wiki_articles (413 Artikel)
- ✅ memory_working, memory_facts, memory_lessons
- ✅ document_index (help/ Dateien)
- ✅ Beliebige Verzeichnisse (via index_directory)
- ❌ KnowledgeDigest (nicht integriert)

**CLI (hub/search.py):**
```bash
bach search "query"          # Volltextsuche
bach search index            # Alle Quellen indexieren
bach search status           # Statistiken
bach search tags             # Alle Tags
```

### C. Befund

✅ **Beide Systeme funktionieren standalone**
✅ **BACH unified_search.py ist produtionsbereit** (SQ047 erfüllt)
✅ **KnowledgeDigest hat Skills/Wiki indexiert** (Aufgabe 4+5 erfüllt)
❌ **KnowledgeDigest ist NICHT in BACH integriert**
❌ **Agenten können KnowledgeDigest NICHT nutzen**

---

## 2. Gap-Analyse

### Gap 1: Import/Dependency

**Status:** ❌ KnowledgeDigest wird nicht in BACH importiert

```bash
$ grep -r "KnowledgeDigest\|knowledge.db" /BACH_v2_vanilla/system/
# Keine Treffer
```

**Benötigt:**
1. KnowledgeDigest als Dependency (`pip install -e ../MODULAR_AGENTS/KnowledgeDigest`)
2. Oder: Code direkt in BACH integrieren

### Gap 2: unified_search Integration

**Status:** ❌ unified_search kennt KnowledgeDigest nicht

**Problem:** `UnifiedSearch.index_all()` indexiert wiki, memory, documents - aber NICHT KnowledgeDigest

**Benötigt:** Neue Methode in unified_search.py:

```python
def index_knowledgedigest(self):
    """
    Index KnowledgeDigest (Skills + Wiki + optional: Wissensdatenbank).

    Reads from knowledge.db and populates search_index.
    """
    # 1. KnowledgeDigest importieren
    from KnowledgeDigest import KnowledgeDigest

    # 2. knowledge.db öffnen
    kd_path = Path(__file__).parent.parent.parent / "MODULAR_AGENTS" / "KnowledgeDigest" / "data" / "knowledge.db"
    kd = KnowledgeDigest(db_path=kd_path)

    # 3. Skills abrufen
    skills = kd.list_skills()
    for skill in skills:
        # skill_name, skill_type, category, path, description, word_count
        self._index_item(
            source="knowledgedigest_skill",
            source_id=skill['skill_name'],
            source_path=skill['path'],
            title=skill['skill_name'],
            content=skill['description'],  # Oder: full content via kd.get_skill()
            category=skill['category'],
            word_count=skill['word_count']
        )

    # 4. Wiki-Einträge abrufen (analog)
    # ...
```

**Oder:** Connector-Layer (siehe Strategie B)

### Gap 3: Daten-Duplikation

**Status:** ⚠️ Wiki-Daten redundant

**Problem:**
- BACH bach.db hat `wiki_articles` (413 Einträge)
- KnowledgeDigest knowledge.db hat `wiki_index` (413 Einträge)
- unified_search indexiert aus `wiki_articles`
- KnowledgeDigest indexiert aus `wiki_index`

**Ergebnis:**
- **Doppelte Indexierung** der gleichen Wiki-Artikel!
- Unnötiger Speicherverbrauch
- Inkonsistenz-Risiko (wenn Wiki aktualisiert wird)

**Lösungen:**

**Option A:** KnowledgeDigest nutzt wiki_articles direkt (kein wiki_index)
**Option B:** unified_search nutzt KnowledgeDigest als Quelle (kein eigenes wiki_articles)
**Option C:** Deduplizierung via content_hash (search_index.content_hash)

### Gap 4: Agent-Zugriff

**Status:** ❌ Agenten können KnowledgeDigest nicht nutzen

**Problem:** Agenten haben keinen direkten Zugriff auf KnowledgeDigest-API

**Lösung-Optionen:**

**Option A: Via unified_search**
```python
# Agent nutzt unified_search (bereits in BACH)
from tools.unified_search import UnifiedSearch

search = UnifiedSearch(bach_db_path)
results = search.search("CRISPR gene editing")
# Ergebnisse enthalten source="knowledgedigest_skill" wenn indexiert
```

**Option B: Via bach_api**
```python
# bach_api.py erweitern
def search_knowledge(query, limit=20):
    """Search via KnowledgeDigest."""
    # Wrapper um KnowledgeDigest.search()
    pass

def get_skill_content(skill_name):
    """Get full skill content from KnowledgeDigest."""
    pass
```

**Option C: Direkt (standalone)**
```python
# Agent importiert KnowledgeDigest direkt
from KnowledgeDigest import KnowledgeDigest

kd = KnowledgeDigest()
results = kd.search("API development")
```

### Gap 5: Schema-Mapping

**Status:** ⚠️ Unterschiedliche Schemata

**KnowledgeDigest Schema (skill_index):**
```sql
id, skill_name, skill_type, category, path,
description, version, content_hash, word_count,
chunk_count, is_active, indexed_at, source_db
```

**unified_search Schema (search_index):**
```sql
id, source, source_id, source_path, title,
content, category, content_hash, word_count,
file_size, indexed_at
```

**Mapping nötig:**
```
skill_name      → source_id (oder title)
skill_type      → category (oder eigenes Feld)
path            → source_path
description     → content (oder full content via chunks)
content_hash    → content_hash (SHA256)
word_count      → word_count
```

**Problem:** KnowledgeDigest hat `chunks` - unified_search hat flache `content`

**Lösungen:**
1. Chunks konkatenieren → content (einfach, Informationsverlust)
2. Jeden Chunk als eigenes search_index Item (granular, viele Rows)
3. Nur Frontmatter/Summary in search_index (kompakt, Volltext via KnowledgeDigest)

---

## 3. Integrations-Strategien

### Strategie A: KnowledgeDigest als Quelle in unified_search

**Ansatz:**
1. `unified_search.py` erweitern um `index_knowledgedigest()` Methode
2. KnowledgeDigest als Library importieren
3. Skills + Wiki aus knowledge.db lesen → search_index schreiben
4. Agenten nutzen unified_search (bereits vorhanden)

**Vorteile:**
- ✅ Agenten haben unified Interface (nur unified_search)
- ✅ Alle Quellen (wiki, memory, skills, documents) in einer Suche
- ✅ Keine Doppel-API (nur unified_search)

**Nachteile:**
- ❌ Daten-Duplikation (knowledge.db + bach.db)
- ❌ Chunk-Granularität verloren (wenn Chunks konkateniert)
- ❌ KnowledgeDigest-Features (search_keywords, get_skill) nicht nutzbar

**Umsetzung:**

1. **unified_search.py erweitern:**
```python
def index_knowledgedigest(self, kd_db_path: Optional[Path] = None):
    """Index Skills and Wiki from KnowledgeDigest."""
    if kd_db_path is None:
        # Default: ../MODULAR_AGENTS/KnowledgeDigest/data/knowledge.db
        kd_db_path = BACH_ROOT.parent / "MODULAR_AGENTS" / "KnowledgeDigest" / "data" / "knowledge.db"

    if not kd_db_path.exists():
        raise FileNotFoundError(f"KnowledgeDigest DB not found: {kd_db_path}")

    # KnowledgeDigest importieren
    sys.path.insert(0, str(kd_db_path.parent.parent))
    from KnowledgeDigest import KnowledgeDigest

    kd = KnowledgeDigest(db_path=kd_db_path)

    # Skills indexieren
    skills = kd.list_skills()
    for skill in skills:
        # Chunks konkatenieren
        full_skill = kd.get_skill(skill['skill_name'])
        content = "\n\n".join(c['content'] for c in full_skill['chunks'])

        self._index_item(
            source="knowledgedigest_skill",
            source_id=skill['skill_name'],
            source_path=skill['path'],
            title=skill['skill_name'],
            content=content,
            category=skill['category'],
            content_hash=skill['content_hash'],
            word_count=skill['word_count']
        )

    # Wiki analog
    # ...
```

2. **index_all() erweitern:**
```python
def index_all(self):
    """Index all sources."""
    self.index_wiki()
    self.index_memory()
    self.index_documents()
    self.index_knowledgedigest()  # NEU
```

3. **CLI erweitern (hub/search.py):**
```bash
bach search index knowledgedigest    # Nur KnowledgeDigest
bach search index all                # Inkl. KnowledgeDigest
```

### Strategie B: Connector-Layer (Dual-API)

**Ansatz:**
1. Neuer Connector: `hub/knowledge_connector.py`
2. Mappt zwischen KnowledgeDigest und unified_search
3. Agenten können beide nutzen (unified_search für einfache Suche, KnowledgeDigest für Skills)

**Vorteile:**
- ✅ KnowledgeDigest-Features bleiben nutzbar (search_keywords, get_skill, chunks)
- ✅ Flexibel (Agent wählt API)
- ✅ Keine Daten-Duplikation nötig (Connector ist nur Proxy)

**Nachteile:**
- ❌ Zwei APIs (Verwirrung?)
- ❌ Komplexität (Connector-Logik)

**Umsetzung:**

1. **hub/knowledge_connector.py:**
```python
class KnowledgeConnector:
    """Bridge between KnowledgeDigest and BACH."""

    def __init__(self, bach_db_path, kd_db_path=None):
        self.bach_db = bach_db_path
        self.kd = KnowledgeDigest(db_path=kd_db_path)

    def search_unified(self, query, limit=20):
        """
        Search via KnowledgeDigest + unified_search.

        Returns: Merged results from both engines.
        """
        # 1. KnowledgeDigest suchen
        kd_results = self.kd.search(query, limit=limit)

        # 2. unified_search suchen
        us = UnifiedSearch(self.bach_db)
        us_results = us.search(query, limit=limit)

        # 3. Merge + Deduplizierung
        # ...

    def get_skill(self, skill_name):
        """Get full skill with chunks from KnowledgeDigest."""
        return self.kd.get_skill(skill_name)
```

2. **bach_api.py erweitern:**
```python
def search_knowledge(query, limit=20, source="unified"):
    """
    Search knowledge base.

    Args:
        query: Search query
        limit: Max results
        source: "unified" (both), "skills" (KnowledgeDigest), "search" (unified_search)
    """
    connector = KnowledgeConnector(BACH_DB)

    if source == "skills":
        return connector.kd.search(query, limit=limit)
    elif source == "search":
        us = UnifiedSearch(BACH_DB)
        return us.search(query, limit=limit)
    else:  # unified
        return connector.search_unified(query, limit=limit)
```

### Strategie C: KnowledgeDigest als Primary (unified_search deprecated)

**Ansatz:**
1. KnowledgeDigest erweitern um alle Quellen (memory, documents)
2. unified_search wird deprecated
3. KnowledgeDigest wird DER Search-Engine

**Vorteile:**
- ✅ Ein System (keine Duplikation)
- ✅ Chunking-Strategie konsistent
- ✅ LLM-Summaries möglich (Vision aus README)

**Nachteile:**
- ❌ Große Code-Änderung (unified_search ersetzen)
- ❌ Breaking Change (unified_search-User)
- ❌ Mehr Aufwand

---

## 4. Empfehlung (Sonnet-Perspektive)

**Strategie A: KnowledgeDigest als Quelle in unified_search** (kurzfristig)

### Begründung:

1. **Minimal-invasiv:** Nur unified_search.py erweitern (eine Datei)
2. **Agent-kompatibel:** Agenten nutzen bereits unified_search
3. **Schnell umsetzbar:** ~2-3h Implementierung
4. **Future-proof:** Kann später zu Strategie C migriert werden

### Implementierungs-Plan:

**Phase 1: unified_search erweitern (Sonnet, 2h)**
1. `index_knowledgedigest()` Methode
2. `index_all()` erweitern
3. Tests (Skills + Wiki indexiert)

**Phase 2: CLI/API (Sonnet, 1h)**
1. `hub/search.py` erweitern (`bach search index knowledgedigest`)
2. `bach_api.py` erweitern (Optional: `search_skills()` Wrapper)

**Phase 3: Dokumentation (Sonnet, 1h)**
1. `docs/knowledge_integration.md`
2. Agent-Beispiele

**Phase 4: Testing (Opus, 2h)**
1. Integration-Tests
2. Performance-Tests (knowledge.db Größe wenn Wissensdatenbank indexiert)
3. Deduplizierung verifizieren (Wiki nicht doppelt)

---

## 5. Abhängigkeiten

### Kritisch ⚠️

**Aufgabe 2: BLOCKED**
- KnowledgeDigest hat aktuell nur Skills (766) + Wiki (413)
- Wissensdatenbank (37.453 Dateien) ist NICHT indexiert
- **Wenn Aufgabe 2 erledigt → knowledge.db wird RIESIG** (155.000 Chunks geschätzt)
- unified_search Integration muss das abkönnen!

**Entscheidungen:**
1. Integration JETZT (nur Skills/Wiki) - später Wissensdatenbank?
2. WARTEN bis Aufgabe 2 erledigt - dann große Integration?

### Optional 📦

**SQ043 (erledigt):**
- SharedMemoryClient-Integration (Aufgabe 3)
- Nicht direkt relevant für KnowledgeDigest

---

## 6. Risiken & Offene Fragen

### Risiken

1. **Daten-Duplikation:**
   - Wiki-Artikel in bach.db UND knowledge.db
   - Lösung: Deduplizierung via content_hash

2. **Performance:**
   - knowledge.db kann groß werden (155k Chunks)
   - Indexierung dauert (bei Wissensdatenbank)
   - unified_search.search() muss performant bleiben

3. **Chunk-Granularität:**
   - KnowledgeDigest hat Chunks (~350 Wörter)
   - unified_search hat flache content
   - Konkatenieren → Verlust von Chunk-Info

### Offene Fragen (für Opus)

1. **Timing:**
   - Integration JETZT (nur Skills/Wiki, klein)?
   - Oder: WARTEN bis Aufgabe 2 (Wissensdatenbank indexiert)?

2. **Chunks:**
   - Konkatenieren → search_index.content (einfach)?
   - Oder: Jeden Chunk als eigenes Item (granular, aber viele Rows)?

3. **Wiki-Deduplizierung:**
   - wiki_articles als Quelle für KnowledgeDigest?
   - Oder: KnowledgeDigest als Quelle für unified_search?
   - Oder: Beide parallel (Deduplizierung via content_hash)?

4. **Dependency:**
   - KnowledgeDigest als pip-Modul?
   - Oder: Code direkt in BACH integrieren?

5. **Future:**
   - Strategie A kurzfristig, Strategie C langfristig?
   - LLM-Summaries (README-Vision) wann?

---

## 7. Code-Beispiele

### unified_search.py Erweiterung

```python
def index_knowledgedigest(self, kd_db_path: Optional[Path] = None) -> Dict[str, int]:
    """
    Index KnowledgeDigest (Skills + Wiki).

    Args:
        kd_db_path: Path to knowledge.db (default: auto-detect)

    Returns:
        Stats dict: {skills: N, wiki: M, chunks_concatenated: K}
    """
    if kd_db_path is None:
        # Default: MODULAR_AGENTS/KnowledgeDigest/data/knowledge.db
        kd_db_path = BACH_ROOT.parent / "MODULAR_AGENTS" / "KnowledgeDigest" / "data" / "knowledge.db"

    if not kd_db_path.exists():
        raise FileNotFoundError(f"KnowledgeDigest DB not found: {kd_db_path}")

    # KnowledgeDigest importieren
    kd_module_path = kd_db_path.parent.parent
    if str(kd_module_path) not in sys.path:
        sys.path.insert(0, str(kd_module_path))

    from KnowledgeDigest import KnowledgeDigest
    kd = KnowledgeDigest(db_path=kd_db_path)

    stats = {"skills": 0, "wiki": 0, "chunks_concatenated": 0}

    # 1. Skills indexieren
    skills = kd.list_skills()
    for skill in skills:
        # Chunks holen
        full_skill = kd.get_skill(skill['skill_name'])
        if not full_skill or 'chunks' not in full_skill:
            continue

        # Chunks konkatenieren
        chunks = full_skill['chunks']
        content = "\n\n".join(c['content'] for c in chunks)
        stats['chunks_concatenated'] += len(chunks)

        # Tags extrahieren (aus path)
        tags = self._extract_tags_from_path(skill['path'])

        # In search_index einfügen
        idx = self._index_item(
            source="knowledgedigest_skill",
            source_id=skill['skill_name'],
            source_path=skill['path'],
            title=skill['skill_name'],
            content=content,
            category=skill['category'] or skill['skill_type'],
            content_hash=skill['content_hash'],
            word_count=skill['word_count']
        )

        # Tags einfügen
        if idx and tags:
            self._add_tags(idx, tags)

        stats['skills'] += 1

    # 2. Wiki analog
    # ... (ähnlich wie Skills)

    return stats
```

### bach_api.py Wrapper

```python
def search_skills(query: str, limit: int = 20, skill_type: str = None):
    """
    Search BACH Skills via KnowledgeDigest (integrated in unified_search).

    Args:
        query: Search query
        limit: Max results
        skill_type: Filter by skill type ('agent', 'protocol', etc.)

    Returns:
        List of skill results from unified_search
    """
    from tools.unified_search import UnifiedSearch

    db_path = Path(__file__).parent / "data" / "bach.db"
    engine = UnifiedSearch(db_path)

    # Suche mit Source-Filter
    results = engine.search(query, limit=limit, sources=["knowledgedigest_skill"])

    # Optional: Nach skill_type filtern (wenn category == skill_type)
    if skill_type:
        results = [r for r in results if r.get('category') == skill_type]

    return results
```

---

## 8. Tests

### Integration-Test

```python
# test_knowledge_integration.py

def test_knowledgedigest_index():
    """Test indexing KnowledgeDigest into unified_search."""
    from tools.unified_search import UnifiedSearch

    engine = UnifiedSearch(BACH_DB)

    # Index KnowledgeDigest
    stats = engine.index_knowledgedigest()

    assert stats['skills'] == 766
    assert stats['wiki'] == 413
    assert stats['chunks_concatenated'] > 2000

def test_skill_search():
    """Test searching for skills."""
    from tools.unified_search import UnifiedSearch

    engine = UnifiedSearch(BACH_DB)

    # Suche nach "entwickler"
    results = engine.search("entwickler")

    # Sollte Skill "entwickler" finden
    assert any(r['source'] == 'knowledgedigest_skill' and r['source_id'] == 'entwickler' for r in results)

def test_wiki_deduplication():
    """Test that Wiki is not duplicated."""
    from tools.unified_search import UnifiedSearch

    engine = UnifiedSearch(BACH_DB)
    conn = engine.get_connection()

    # Anzahl "wiki" Quellen
    wiki_count = conn.execute("SELECT COUNT(*) FROM search_index WHERE source = 'wiki'").fetchone()[0]

    # Anzahl "knowledgedigest_wiki" Quellen
    kd_wiki_count = conn.execute("SELECT COUNT(*) FROM search_index WHERE source = 'knowledgedigest_wiki'").fetchone()[0]

    # Beide sollten NICHT gleichzeitig existieren (oder: Deduplizierung via hash)
    # ...
```

---

## 9. Nächste Schritte

### Wenn Opus übernimmt (empfohlen):

1. **Entscheidungen treffen:**
   - Timing: Jetzt oder nach Aufgabe 2?
   - Chunks: Konkatenieren oder granular?
   - Wiki: Deduplizierung wie?

2. **Phase 1-4 durchführen** (siehe Abschnitt 4)

3. **Tests** (Integration + Performance)

4. **Dokumentation** für Agenten

### Wenn Sonnet weitermacht (mit Vorgaben):

1. **Phase 1:** `index_knowledgedigest()` implementieren
2. **Phase 2:** CLI/API erweitern
3. **Phase 3:** Dokumentation

**BLOCKED bis Aufgabe 2** entschieden ist (Wissensdatenbank-Integration)

---

**Erstellt:** 2026-02-21 12:20
**Von:** Sonnet Worker (Vorbereitungsarbeit)
**Für:** Opus Architect
**Status:** AWAITING_DECISION
**Dependency:** Aufgabe 2 (Wissensdatenbank-Indexierung)
