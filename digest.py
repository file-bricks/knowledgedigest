# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Haupt-Klasse.

High-Level API fuer die Wissensdatenbank:
    - index_skills(bach_db_path) -- BACH Skills einlesen und indexieren
    - index_wikis(bach_db_path)  -- BACH Wikis einlesen und indexieren
    - ingest(path)               -- Dokumente verarbeiten (PDF/DOCX/TXT/MD/HTML)
    - summarize(limit)           -- LLM-Zusammenfassungen generieren (Haiku)
    - search(query)              -- FTS5-Suche ueber Skills
    - search_wikis(query)        -- FTS5-Suche ueber Wikis
    - search_all(query)          -- Unified Search ueber alles
    - get_status()               -- Index-Status

Usage:
    from KnowledgeDigest import KnowledgeDigest

    kd = KnowledgeDigest()
    kd.ingest("/path/to/documents/")
    kd.summarize(limit=10)
    results = kd.search_all("machine learning")
"""

__all__ = ["KnowledgeDigest"]

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any

from .schema import ensure_schema
from .indexer import SkillIndexer
from .wiki_indexer import WikiIndexer
from .ingestor import DocumentIngestor
from .summarizer import Summarizer

# Default: knowledge.db im data/ Unterordner
_DEFAULT_DB = Path(__file__).parent / "data" / "knowledge.db"

# BACH-Standard-Pfad (Windows)
_DEFAULT_BACH_DB = Path(r"C:\Users\lukas\OneDrive\KI&AI\BACH_v2_vanilla\system\data\bach.db")


class KnowledgeDigest:
    """Wissensdatenbank mit FTS5-Suche und LLM-Summarization.

    Indexiert BACH-Skills, Wiki-Artikel und ingested Dokumente
    in einer eigenen SQLite-DB. Chunked den Content fuer
    granulare Suche (~400 Token pro Chunk).

    Usage:
        kd = KnowledgeDigest()
        kd.ingest("/path/to/docs/")
        kd.summarize(limit=10)
        results = kd.search_all("CRISPR")
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialisiert KnowledgeDigest.

        Args:
            db_path: Pfad zur knowledge.db (Default: data/knowledge.db)
        """
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._indexer = SkillIndexer(self.db_path)
        self._wiki_indexer = WikiIndexer(self.db_path)
        self._ingestor = DocumentIngestor(self.db_path)
        self._summarizer = Summarizer(self.db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Oeffnet DB-Connection mit Schema-Sicherstellung."""
        return ensure_schema(self.db_path)

    # ------------------------------------------------------------------
    # INDEXIERUNG
    # ------------------------------------------------------------------

    def index_skills(self, bach_db_path: Optional[str] = None, *,
                     force: bool = False,
                     chunk_size: int = 350,
                     overlap: int = 0) -> Dict[str, Any]:
        """Indexiert BACH-Skills aus bach.db.

        Args:
            bach_db_path: Pfad zur bach.db (Default: BACH Standard-Pfad)
            force: Bestehenden Index komplett neu aufbauen
            chunk_size: Woerter pro Chunk
            overlap: Overlap zwischen Chunks

        Returns:
            Statistiken ueber die Indexierung
        """
        path = Path(bach_db_path) if bach_db_path else _DEFAULT_BACH_DB
        return self._indexer.index_from_bach(
            path, chunk_size=chunk_size, overlap=overlap, force=force
        )

    # ------------------------------------------------------------------
    # SUCHE
    # ------------------------------------------------------------------

    def search(self, query: str, *, limit: int = 20,
               skill_type: Optional[str] = None,
               category: Optional[str] = None) -> List[Dict[str, Any]]:
        """FTS5-basierte Suche ueber indexierte Skills.

        Args:
            query: Suchbegriff(e) -- FTS5-Syntax unterstuetzt
            limit: Maximale Ergebnisse (Default: 20)
            skill_type: Filter nach Skill-Typ (z.B. 'agent', 'protocol')
            category: Filter nach Kategorie

        Returns:
            Liste von Ergebnis-Dicts:
            [{
                'skill_name': 'entwickler',
                'skill_type': 'profile',
                'category': 'agent',
                'snippet': '...matching text...',
                'relevance': -1.23,
                'chunk_index': 1,
                'word_count': 456,
            }, ...]
        """
        conn = self._get_conn()
        try:
            # Filter-Clauses aufbauen
            where_parts = []
            params: list = [query]

            if skill_type:
                where_parts.append("si.skill_type = ?")
                params.append(skill_type)
            if category:
                where_parts.append("si.category = ?")
                params.append(category)

            where_sql = ""
            if where_parts:
                where_sql = "AND " + " AND ".join(where_parts)

            params.append(limit)

            sql = f"""
                SELECT
                    si.skill_name,
                    si.skill_type,
                    si.category,
                    si.path,
                    si.description,
                    si.word_count,
                    sc.chunk_index,
                    sc.is_frontmatter,
                    snippet(skill_fts, 1, '>>>', '<<<', '...', 30) as snippet,
                    skill_fts.rank as relevance
                FROM skill_fts
                JOIN skill_chunks sc ON skill_fts.rowid = sc.id
                JOIN skill_index si ON sc.skill_id = si.id
                WHERE skill_fts MATCH ?
                {where_sql}
                ORDER BY skill_fts.rank
                LIMIT ?
            """

            rows = conn.execute(sql, params).fetchall()

            results = []
            seen_skills = set()
            for row in rows:
                # Deduplizieren: nur bestes Ergebnis pro Skill
                name = row['skill_name']
                if name in seen_skills:
                    continue
                seen_skills.add(name)

                results.append({
                    'skill_name': name,
                    'skill_type': row['skill_type'],
                    'category': row['category'],
                    'path': row['path'],
                    'description': row['description'],
                    'snippet': row['snippet'],
                    'relevance': row['relevance'],
                    'chunk_index': row['chunk_index'],
                    'word_count': row['word_count'],
                })

            return results

        except Exception:
            # FTS5 Fallback: LIKE-Suche
            return self._search_fallback(conn, query, limit, skill_type, category)
        finally:
            conn.close()

    def _search_fallback(self, conn: sqlite3.Connection, query: str,
                         limit: int, skill_type: Optional[str],
                         category: Optional[str]) -> List[Dict[str, Any]]:
        """LIKE-basierte Fallback-Suche wenn FTS5 fehlschlaegt."""
        where_parts = ["(sc.content LIKE ? OR si.skill_name LIKE ?)"]
        like = f"%{query}%"
        params: list = [like, like]

        if skill_type:
            where_parts.append("si.skill_type = ?")
            params.append(skill_type)
        if category:
            where_parts.append("si.category = ?")
            params.append(category)

        params.append(limit)

        try:
            rows = conn.execute(f"""
                SELECT DISTINCT
                    si.skill_name, si.skill_type, si.category,
                    si.path, si.description, si.word_count
                FROM skill_index si
                LEFT JOIN skill_chunks sc ON sc.skill_id = si.id
                WHERE {' AND '.join(where_parts)}
                LIMIT ?
            """, params).fetchall()

            return [{
                'skill_name': r['skill_name'],
                'skill_type': r['skill_type'],
                'category': r['category'],
                'path': r['path'],
                'description': r['description'],
                'snippet': '(LIKE-Fallback)',
                'relevance': 0,
                'chunk_index': 0,
                'word_count': r['word_count'],
            } for r in rows]
        except Exception:
            return []

    def search_keywords(self, keyword: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        """Suche ueber extrahierte Keywords.

        Args:
            keyword: Keyword (exakt oder Prefix-Match)
            limit: Maximale Ergebnisse

        Returns:
            Skills die dieses Keyword enthalten
        """
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT si.skill_name, si.skill_type, si.category,
                       si.description, si.word_count,
                       GROUP_CONCAT(sk.keyword) as matching_keywords
                FROM skill_keywords sk
                JOIN skill_index si ON sk.skill_id = si.id
                WHERE sk.keyword LIKE ?
                GROUP BY si.id
                ORDER BY si.skill_name
                LIMIT ?
            """, (f"{keyword.lower()}%", limit)).fetchall()

            return [{
                'skill_name': r['skill_name'],
                'skill_type': r['skill_type'],
                'category': r['category'],
                'description': r['description'],
                'word_count': r['word_count'],
                'matching_keywords': (r['matching_keywords'] or '').split(','),
            } for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # EINZELABRUF
    # ------------------------------------------------------------------

    def get_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Ruft einen einzelnen Skill mit allen Chunks ab.

        Args:
            skill_name: Name des Skills (exakt)

        Returns:
            Dict mit Skill-Details und Chunks, oder None
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM skill_index WHERE skill_name = ?",
                (skill_name,)
            ).fetchone()

            if not row:
                return None

            skill_id = row['id']

            # Chunks laden
            chunks = conn.execute(
                "SELECT chunk_index, content, token_count, is_frontmatter "
                "FROM skill_chunks WHERE skill_id = ? ORDER BY chunk_index",
                (skill_id,)
            ).fetchall()

            # Keywords laden
            keywords = conn.execute(
                "SELECT keyword, source FROM skill_keywords WHERE skill_id = ?",
                (skill_id,)
            ).fetchall()

            return {
                'skill_name': row['skill_name'],
                'skill_type': row['skill_type'],
                'category': row['category'],
                'path': row['path'],
                'description': row['description'],
                'version': row['version'],
                'word_count': row['word_count'],
                'chunk_count': row['chunk_count'],
                'is_active': bool(row['is_active']),
                'indexed_at': row['indexed_at'],
                'chunks': [{
                    'index': c['chunk_index'],
                    'content': c['content'],
                    'token_count': c['token_count'],
                    'is_frontmatter': bool(c['is_frontmatter']),
                } for c in chunks],
                'keywords': [k['keyword'] for k in keywords],
            }
        finally:
            conn.close()

    def list_skills(self, *, skill_type: Optional[str] = None,
                    category: Optional[str] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Listet indexierte Skills auf.

        Args:
            skill_type: Filter nach Typ
            category: Filter nach Kategorie
            limit: Maximale Ergebnisse

        Returns:
            Liste von Skill-Zusammenfassungen
        """
        conn = self._get_conn()
        try:
            where_parts = []
            params: list = []

            if skill_type:
                where_parts.append("skill_type = ?")
                params.append(skill_type)
            if category:
                where_parts.append("category = ?")
                params.append(category)

            where_sql = ""
            if where_parts:
                where_sql = "WHERE " + " AND ".join(where_parts)

            params.append(limit)

            rows = conn.execute(f"""
                SELECT skill_name, skill_type, category, description,
                       word_count, chunk_count, indexed_at
                FROM skill_index
                {where_sql}
                ORDER BY skill_name
                LIMIT ?
            """, params).fetchall()

            return [{
                'skill_name': r['skill_name'],
                'skill_type': r['skill_type'],
                'category': r['category'],
                'description': r['description'],
                'word_count': r['word_count'],
                'chunk_count': r['chunk_count'],
                'indexed_at': r['indexed_at'],
            } for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Gibt umfassende Index-Statistiken zurueck."""
        skill_status = self._indexer.get_index_status()
        wiki_status = self._wiki_indexer.get_index_status()
        doc_status = self._ingestor.get_ingest_status()
        queue_status = self._summarizer.get_queue_status()

        # DB-Groesse
        db_info = {}
        if self.db_path.exists():
            db_info['db_path'] = str(self.db_path)
            db_info['db_size_kb'] = round(self.db_path.stat().st_size / 1024, 1)
        else:
            db_info['db_path'] = str(self.db_path)
            db_info['db_size_kb'] = 0

        return {
            **db_info,
            'skills': skill_status,
            'wikis': wiki_status,
            'documents': doc_status,
            'queue': queue_status,
        }

    def close(self):
        """Schliesst alle offenen Connections."""
        self._indexer.close()
        self._wiki_indexer.close()
        self._ingestor.close()
        self._summarizer.close()

    # ==================================================================
    # DOCUMENT INGESTION
    # ==================================================================

    def ingest(self, path: str | Path, *,
               archive: bool = True,
               chunk_size: int = 350,
               recursive: bool = False) -> Dict[str, Any]:
        """Verarbeitet Dokumente (Dateien oder Ordner).

        Args:
            path: Datei oder Ordner
            archive: Originale nach archive/ verschieben
            chunk_size: Woerter pro Chunk
            recursive: Unterordner mit einbeziehen

        Returns:
            Statistiken
        """
        p = Path(path)
        if p.is_file():
            return self._ingestor.ingest_file(
                p, archive=archive, chunk_size=chunk_size
            )
        elif p.is_dir():
            return self._ingestor.ingest_directory(
                p, archive=archive, chunk_size=chunk_size, recursive=recursive
            )
        else:
            return {'error': f'Pfad nicht gefunden: {path}'}

    # ==================================================================
    # LLM SUMMARIZATION
    # ==================================================================

    def summarize(self, *, limit: int = 10,
                  delay: float = 0.5) -> Dict[str, Any]:
        """Verarbeitet pending Queue-Items mit Haiku LLM.

        Args:
            limit: Maximale Queue-Items pro Durchlauf
            delay: Pause zwischen API-Calls (Sekunden)

        Returns:
            Statistiken
        """
        return self._summarizer.summarize_queue(limit=limit, delay=delay)

    def enqueue_all(self) -> Dict[str, int]:
        """Erstellt Queue-Eintraege fuer alle Skills und Wikis."""
        skills = self._summarizer.enqueue_skills()
        wikis = self._summarizer.enqueue_wikis()
        return {'skills_enqueued': skills, 'wikis_enqueued': wikis}

    def get_queue_status(self) -> Dict[str, Any]:
        """Queue-Statistiken."""
        return self._summarizer.get_queue_status()

    # ==================================================================
    # UNIFIED SEARCH
    # ==================================================================

    def search_all(self, query: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        """Sucht ueber Skills, Wikis und Dokumente gleichzeitig.

        Args:
            query: Suchbegriff(e) -- FTS5-Syntax
            limit: Maximale Ergebnisse pro Quelle

        Returns:
            Zusammengefuehrte und nach Relevanz sortierte Ergebnisse
        """
        results = []

        # Skills durchsuchen
        try:
            skill_results = self.search(query, limit=limit)
            for r in skill_results:
                results.append({
                    'source': 'skill',
                    'name': r['skill_name'],
                    'type': r.get('skill_type', ''),
                    'snippet': r.get('snippet', ''),
                    'relevance': r.get('relevance', 0),
                    'word_count': r.get('word_count', 0),
                })
        except Exception:
            pass

        # Wikis durchsuchen
        try:
            wiki_results = self.search_wikis(query, limit=limit)
            for r in wiki_results:
                results.append({
                    'source': 'wiki',
                    'name': r.get('title', r.get('wiki_path', '')),
                    'type': r.get('category', ''),
                    'snippet': r.get('snippet', ''),
                    'relevance': r.get('relevance', 0),
                    'word_count': r.get('word_count', 0),
                })
        except Exception:
            pass

        # Dokumente durchsuchen
        try:
            doc_results = self._search_documents(query, limit=limit)
            results.extend(doc_results)
        except Exception:
            pass

        # Nach Relevanz sortieren (niedrigerer BM25-Rank = besser)
        results.sort(key=lambda x: x.get('relevance', 0))

        return results[:limit]

    def _search_documents(self, query: str, *,
                          limit: int = 20) -> List[Dict[str, Any]]:
        """FTS5-Suche ueber ingested Dokumente."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT
                    d.filename,
                    d.file_type,
                    d.word_count,
                    dc.chunk_index,
                    snippet(document_fts, 1, '>>>', '<<<', '...', 30) as snippet,
                    document_fts.rank as relevance
                FROM document_fts
                JOIN document_chunks dc ON document_fts.rowid = dc.id
                JOIN documents d ON dc.doc_id = d.id
                WHERE document_fts MATCH ?
                ORDER BY document_fts.rank
                LIMIT ?
            """, (query, limit)).fetchall()

            results = []
            seen = set()
            for row in rows:
                name = row['filename']
                if name in seen:
                    continue
                seen.add(name)
                results.append({
                    'source': 'document',
                    'name': name,
                    'type': row['file_type'],
                    'snippet': row['snippet'],
                    'relevance': row['relevance'],
                    'word_count': row['word_count'],
                })
            return results
        except Exception:
            return []
        finally:
            conn.close()

    # ==================================================================
    # WIKI-ARTIKEL INDEXIERUNG
    # ==================================================================

    def index_wikis(self, bach_db_path: Optional[str] = None, *,
                    force: bool = False,
                    chunk_size: int = 350,
                    overlap: int = 0) -> Dict[str, Any]:
        """Indexiert BACH Wiki-Artikel aus bach.db.

        Args:
            bach_db_path: Pfad zur bach.db (Default: BACH Standard-Pfad)
            force: Bestehenden Index komplett neu aufbauen
            chunk_size: Woerter pro Chunk
            overlap: Overlap zwischen Chunks

        Returns:
            Statistiken ueber die Indexierung
        """
        path = Path(bach_db_path) if bach_db_path else _DEFAULT_BACH_DB
        return self._wiki_indexer.index_from_bach(
            path, chunk_size=chunk_size, overlap=overlap, force=force
        )

    # ==================================================================
    # WIKI-SUCHE
    # ==================================================================

    def search_wikis(self, query: str, *, limit: int = 20,
                     category: Optional[str] = None) -> List[Dict[str, Any]]:
        """FTS5-basierte Suche ueber indexierte Wiki-Artikel.

        Args:
            query: Suchbegriff(e) -- FTS5-Syntax unterstuetzt
            limit: Maximale Ergebnisse (Default: 20)
            category: Filter nach Kategorie

        Returns:
            Liste von Ergebnis-Dicts:
            [{
                'wiki_path': 'help/wiki/ollama.txt',
                'title': 'Ollama LLM-Server',
                'category': 'wiki',
                'snippet': '...matching text...',
                'relevance': -1.23,
                'chunk_index': 1,
                'word_count': 456,
            }, ...]
        """
        conn = self._get_conn()
        try:
            # Filter-Clauses aufbauen
            where_parts = []
            params: list = [query]

            if category:
                where_parts.append("wi.category = ?")
                params.append(category)

            where_sql = ""
            if where_parts:
                where_sql = "AND " + " AND ".join(where_parts)

            params.append(limit)

            sql = f"""
                SELECT
                    wi.wiki_path,
                    wi.title,
                    wi.category,
                    wi.tags,
                    wi.word_count,
                    wi.last_modified,
                    wc.chunk_index,
                    snippet(wiki_fts, 2, '>>>', '<<<', '...', 30) as snippet,
                    wiki_fts.rank as relevance
                FROM wiki_fts
                JOIN wiki_chunks wc ON wiki_fts.rowid = wc.id
                JOIN wiki_index wi ON wc.wiki_id = wi.id
                WHERE wiki_fts MATCH ?
                {where_sql}
                ORDER BY wiki_fts.rank
                LIMIT ?
            """

            rows = conn.execute(sql, params).fetchall()

            results = []
            seen_wikis = set()
            for row in rows:
                # Deduplizieren: nur bestes Ergebnis pro Wiki
                path = row['wiki_path']
                if path in seen_wikis:
                    continue
                seen_wikis.add(path)

                results.append({
                    'wiki_path': path,
                    'title': row['title'],
                    'category': row['category'],
                    'tags': row['tags'],
                    'snippet': row['snippet'],
                    'relevance': row['relevance'],
                    'chunk_index': row['chunk_index'],
                    'word_count': row['word_count'],
                    'last_modified': row['last_modified'],
                })

            return results

        except Exception:
            # FTS5 Fallback: LIKE-Suche
            return self._search_wikis_fallback(conn, query, limit, category)
        finally:
            conn.close()

    def _search_wikis_fallback(self, conn: sqlite3.Connection, query: str,
                               limit: int, category: Optional[str]) -> List[Dict[str, Any]]:
        """LIKE-basierte Fallback-Suche wenn FTS5 fehlschlaegt."""
        where_parts = ["(wc.content LIKE ? OR wi.title LIKE ?)"]
        like = f"%{query}%"
        params: list = [like, like]

        if category:
            where_parts.append("wi.category = ?")
            params.append(category)

        params.append(limit)

        try:
            rows = conn.execute(f"""
                SELECT DISTINCT
                    wi.wiki_path, wi.title, wi.category, wi.tags,
                    wi.word_count, wi.last_modified
                FROM wiki_index wi
                LEFT JOIN wiki_chunks wc ON wc.wiki_id = wi.id
                WHERE {' AND '.join(where_parts)}
                LIMIT ?
            """, params).fetchall()

            return [{
                'wiki_path': r['wiki_path'],
                'title': r['title'],
                'category': r['category'],
                'tags': r['tags'],
                'snippet': '(LIKE-Fallback)',
                'relevance': 0,
                'chunk_index': 0,
                'word_count': r['word_count'],
                'last_modified': r['last_modified'],
            } for r in rows]
        except Exception:
            return []

    def search_wiki_keywords(self, keyword: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        """Suche ueber extrahierte Wiki-Keywords.

        Args:
            keyword: Keyword (exakt oder Prefix-Match)
            limit: Maximale Ergebnisse

        Returns:
            Wikis die dieses Keyword enthalten
        """
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT wi.wiki_path, wi.title, wi.category,
                       wi.word_count, wi.last_modified,
                       GROUP_CONCAT(wk.keyword) as matching_keywords
                FROM wiki_keywords wk
                JOIN wiki_index wi ON wk.wiki_id = wi.id
                WHERE wk.keyword LIKE ?
                GROUP BY wi.id
                ORDER BY wi.title
                LIMIT ?
            """, (f"{keyword.lower()}%", limit)).fetchall()

            return [{
                'wiki_path': r['wiki_path'],
                'title': r['title'],
                'category': r['category'],
                'word_count': r['word_count'],
                'last_modified': r['last_modified'],
                'matching_keywords': (r['matching_keywords'] or '').split(','),
            } for r in rows]
        finally:
            conn.close()

    # ==================================================================
    # WIKI-EINZELABRUF
    # ==================================================================

    def get_wiki(self, wiki_path: str) -> Optional[Dict[str, Any]]:
        """Ruft einen einzelnen Wiki-Artikel mit allen Chunks ab.

        Args:
            wiki_path: Pfad des Wiki-Artikels (exakt)

        Returns:
            Dict mit Wiki-Details und Chunks, oder None
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM wiki_index WHERE wiki_path = ?",
                (wiki_path,)
            ).fetchone()

            if not row:
                return None

            wiki_id = row['id']

            # Chunks laden
            chunks = conn.execute(
                "SELECT chunk_index, content, token_count "
                "FROM wiki_chunks WHERE wiki_id = ? ORDER BY chunk_index",
                (wiki_id,)
            ).fetchall()

            # Keywords laden
            keywords = conn.execute(
                "SELECT keyword, source FROM wiki_keywords WHERE wiki_id = ?",
                (wiki_id,)
            ).fetchall()

            return {
                'wiki_path': row['wiki_path'],
                'title': row['title'],
                'category': row['category'],
                'tags': row['tags'],
                'word_count': row['word_count'],
                'chunk_count': row['chunk_count'],
                'last_modified': row['last_modified'],
                'indexed_at': row['indexed_at'],
                'chunks': [{
                    'index': c['chunk_index'],
                    'content': c['content'],
                    'token_count': c['token_count'],
                } for c in chunks],
                'keywords': [k['keyword'] for k in keywords],
            }
        finally:
            conn.close()

    def list_wikis(self, *, category: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Listet indexierte Wiki-Artikel auf.

        Args:
            category: Filter nach Kategorie
            limit: Maximale Ergebnisse

        Returns:
            Liste von Wiki-Zusammenfassungen
        """
        conn = self._get_conn()
        try:
            where_parts = []
            params: list = []

            if category:
                where_parts.append("category = ?")
                params.append(category)

            where_sql = ""
            if where_parts:
                where_sql = "WHERE " + " AND ".join(where_parts)

            params.append(limit)

            rows = conn.execute(f"""
                SELECT wiki_path, title, category, tags,
                       word_count, chunk_count, last_modified, indexed_at
                FROM wiki_index
                {where_sql}
                ORDER BY title
                LIMIT ?
            """, params).fetchall()

            return [{
                'wiki_path': r['wiki_path'],
                'title': r['title'],
                'category': r['category'],
                'tags': r['tags'],
                'word_count': r['word_count'],
                'chunk_count': r['chunk_count'],
                'last_modified': r['last_modified'],
                'indexed_at': r['indexed_at'],
            } for r in rows]
        finally:
            conn.close()


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    """CLI-Entrypoint fuer Standalone-Nutzung."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="KnowledgeDigest -- Wissensdatenbank mit LLM-Summarization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Ingestion & Summarization:
  python -m KnowledgeDigest ingest data/inbox/       # Dokumente verarbeiten
  python -m KnowledgeDigest ingest document.pdf      # Einzeldatei
  python -m KnowledgeDigest summarize --limit 10     # Queue abarbeiten (Haiku)
  python -m KnowledgeDigest enqueue                  # Skills+Wikis in Queue
  python -m KnowledgeDigest queue                    # Queue-Status

Unified Search:
  python -m KnowledgeDigest search-all "topic"       # Skills+Wikis+Docs

Skills:
  python -m KnowledgeDigest index                    # Skills indexieren
  python -m KnowledgeDigest search "agent"           # Skill-Suche

Wikis:
  python -m KnowledgeDigest index-wikis              # Wikis indexieren
  python -m KnowledgeDigest search-wikis "ollama"    # Wiki-Suche

Status:
  python -m KnowledgeDigest status                   # Gesamtstatus
"""
    )

    sub = parser.add_subparsers(dest="cmd")

    # index
    idx = sub.add_parser("index", help="BACH-Skills indexieren")
    idx.add_argument("--bach-db", help="Pfad zur bach.db")
    idx.add_argument("--force", action="store_true", help="Index komplett neu aufbauen")
    idx.add_argument("--chunk-size", type=int, default=350, help="Woerter pro Chunk")
    idx.add_argument("--overlap", type=int, default=0, help="Overlap in Woertern")

    # search
    s = sub.add_parser("search", help="FTS5-Suche")
    s.add_argument("query")
    s.add_argument("--type", "-t", help="Skill-Typ filtern")
    s.add_argument("--category", "-c", help="Kategorie filtern")
    s.add_argument("--limit", "-l", type=int, default=20)

    # get
    g = sub.add_parser("get", help="Skill-Details abrufen")
    g.add_argument("name", help="Skill-Name")

    # status
    sub.add_parser("status", help="Index-Status")

    # keywords
    kw = sub.add_parser("keywords", help="Keyword-Suche")
    kw.add_argument("keyword")
    kw.add_argument("--limit", "-l", type=int, default=20)

    # list
    ls = sub.add_parser("list", help="Skills auflisten")
    ls.add_argument("--type", "-t", help="Skill-Typ filtern")
    ls.add_argument("--category", "-c", help="Kategorie filtern")
    ls.add_argument("--limit", "-l", type=int, default=50)

    # ========== WIKI-BEFEHLE ==========

    # index-wikis
    idx_w = sub.add_parser("index-wikis", help="BACH Wiki-Artikel indexieren")
    idx_w.add_argument("--bach-db", help="Pfad zur bach.db")
    idx_w.add_argument("--force", action="store_true", help="Index komplett neu aufbauen")
    idx_w.add_argument("--chunk-size", type=int, default=350, help="Woerter pro Chunk")
    idx_w.add_argument("--overlap", type=int, default=0, help="Overlap in Woertern")

    # search-wikis
    s_w = sub.add_parser("search-wikis", help="FTS5-Suche in Wikis")
    s_w.add_argument("query")
    s_w.add_argument("--category", "-c", help="Kategorie filtern")
    s_w.add_argument("--limit", "-l", type=int, default=20)

    # get-wiki
    g_w = sub.add_parser("get-wiki", help="Wiki-Artikel-Details abrufen")
    g_w.add_argument("path", help="Wiki-Pfad")

    # wiki-keywords
    kw_w = sub.add_parser("wiki-keywords", help="Wiki-Keyword-Suche")
    kw_w.add_argument("keyword")
    kw_w.add_argument("--limit", "-l", type=int, default=20)

    # list-wikis
    ls_w = sub.add_parser("list-wikis", help="Wiki-Artikel auflisten")
    ls_w.add_argument("--category", "-c", help="Kategorie filtern")
    ls_w.add_argument("--limit", "-l", type=int, default=50)

    # ========== INGESTION & SUMMARIZATION ==========

    # ingest
    ing = sub.add_parser("ingest", help="Dokumente verarbeiten")
    ing.add_argument("path", nargs="?", help="Datei oder Ordner (Default: data/inbox/)")
    ing.add_argument("--no-archive", action="store_true", help="Originale nicht verschieben")
    ing.add_argument("--recursive", "-r", action="store_true", help="Unterordner einbeziehen")
    ing.add_argument("--chunk-size", type=int, default=350, help="Woerter pro Chunk")

    # summarize
    summ = sub.add_parser("summarize", help="LLM-Summarization (Haiku)")
    summ.add_argument("--limit", "-l", type=int, default=10, help="Max Queue-Items")
    summ.add_argument("--delay", type=float, default=0.5, help="Pause zwischen Calls (s)")

    # enqueue
    sub.add_parser("enqueue", help="Skills+Wikis in Summarization-Queue")

    # queue
    sub.add_parser("queue", help="Queue-Status anzeigen")

    # search-all
    sa = sub.add_parser("search-all", help="Unified Search (Skills+Wikis+Docs)")
    sa.add_argument("query")
    sa.add_argument("--limit", "-l", type=int, default=20)

    args = parser.parse_args()
    kd = KnowledgeDigest()

    if args.cmd == "index":
        stats = kd.index_skills(
            args.bach_db, force=args.force,
            chunk_size=args.chunk_size, overlap=args.overlap,
        )
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.cmd == "search":
        results = kd.search(
            args.query, limit=args.limit,
            skill_type=args.type, category=args.category,
        )
        if not results:
            print("Keine Treffer.")
        for r in results:
            print(f"  [{r['skill_type']}] {r['skill_name']}")
            if r.get('description'):
                print(f"    {r['description']}")
            if r.get('snippet'):
                print(f"    {r['snippet'][:120]}")
            print()

    elif args.cmd == "get":
        skill = kd.get_skill(args.name)
        if skill:
            # Chunks nur Uebersicht (nicht vollen Content)
            display = dict(skill)
            display['chunks'] = [
                {'index': c['index'], 'tokens': c['token_count'],
                 'frontmatter': c['is_frontmatter'],
                 'preview': c['content'][:80] + '...' if len(c['content']) > 80 else c['content']}
                for c in skill['chunks']
            ]
            print(json.dumps(display, indent=2, ensure_ascii=False))
        else:
            print(f"Skill '{args.name}' nicht gefunden.")

    elif args.cmd == "status":
        status = kd.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    elif args.cmd == "keywords":
        results = kd.search_keywords(args.keyword, limit=args.limit)
        if not results:
            print("Keine Treffer.")
        for r in results:
            kws = ', '.join(r['matching_keywords'][:5])
            print(f"  [{r['skill_type']}] {r['skill_name']} -- {kws}")

    elif args.cmd == "list":
        results = kd.list_skills(
            skill_type=args.type, category=args.category, limit=args.limit,
        )
        if not results:
            print("Keine Skills gefunden.")
        for r in results:
            chunks_info = f" ({r['chunk_count']} chunks)" if r['chunk_count'] else ""
            print(f"  [{r['skill_type']}] {r['skill_name']}{chunks_info}")

    # ========== WIKI-BEFEHLE ==========

    elif args.cmd == "index-wikis":
        stats = kd.index_wikis(
            args.bach_db, force=args.force,
            chunk_size=args.chunk_size, overlap=args.overlap,
        )
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.cmd == "search-wikis":
        results = kd.search_wikis(
            args.query, limit=args.limit, category=args.category,
        )
        if not results:
            print("Keine Treffer.")
        for r in results:
            cat = f"[{r['category']}]" if r['category'] else ""
            print(f"  {cat} {r['title']}")
            print(f"    {r['wiki_path']}")
            if r.get('snippet'):
                print(f"    {r['snippet'][:120]}")
            print()

    elif args.cmd == "get-wiki":
        wiki = kd.get_wiki(args.path)
        if wiki:
            # Chunks nur Uebersicht (nicht vollen Content)
            display = dict(wiki)
            display['chunks'] = [
                {'index': c['index'], 'tokens': c['token_count'],
                 'preview': c['content'][:80] + '...' if len(c['content']) > 80 else c['content']}
                for c in wiki['chunks']
            ]
            print(json.dumps(display, indent=2, ensure_ascii=False))
        else:
            print(f"Wiki '{args.path}' nicht gefunden.")

    elif args.cmd == "wiki-keywords":
        results = kd.search_wiki_keywords(args.keyword, limit=args.limit)
        if not results:
            print("Keine Treffer.")
        for r in results:
            kws = ', '.join(r['matching_keywords'][:5])
            print(f"  {r['title']} -- {kws}")

    elif args.cmd == "list-wikis":
        results = kd.list_wikis(category=args.category, limit=args.limit)
        if not results:
            print("Keine Wikis gefunden.")
        for r in results:
            chunks_info = f" ({r['chunk_count']} chunks)" if r['chunk_count'] else ""
            cat = f"[{r['category']}]" if r['category'] else ""
            print(f"  {cat} {r['title']}{chunks_info}")
            print(f"    {r['wiki_path']}")

    # ========== INGESTION & SUMMARIZATION ==========

    elif args.cmd == "ingest":
        path = Path(args.path) if args.path else None
        if path:
            result = kd.ingest(
                path, archive=not args.no_archive,
                chunk_size=args.chunk_size, recursive=args.recursive,
            )
        else:
            # Default: data/inbox/
            result = kd.ingest(
                _DEFAULT_DB.parent / "inbox",
                archive=not args.no_archive,
                chunk_size=args.chunk_size, recursive=args.recursive,
            )
        if isinstance(result, dict) and 'files' in result:
            # Directory result
            print(f"Verarbeitet: {result.get('ingested', 0)} | "
                  f"Uebersprungen: {result.get('skipped', 0)} | "
                  f"Fehler: {result.get('errors', 0)}")
            print(f"Chunks: {result.get('total_chunks', 0)} | "
                  f"Woerter: {result.get('total_words', 0)} | "
                  f"Dauer: {result.get('duration_ms', 0)}ms")
            if result.get('errors', 0) > 0:
                for f in result['files']:
                    if f['status'] == 'error':
                        print(f"  FEHLER: {f['filename']}: {f['error']}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.cmd == "summarize":
        result = kd.summarize(limit=args.limit, delay=args.delay)
        print(f"Verarbeitet: {result.get('processed', 0)} | "
              f"Fehler: {result.get('errors', 0)} | "
              f"Dauer: {result.get('duration_ms', 0)}ms")
        print(f"Tokens: {result.get('total_input_tokens', 0)} in / "
              f"{result.get('total_output_tokens', 0)} out | "
              f"Kosten: ~${result.get('estimated_cost_usd', 0)}")

    elif args.cmd == "enqueue":
        result = kd.enqueue_all()
        print(f"Skills enqueued: {result['skills_enqueued']}")
        print(f"Wikis enqueued: {result['wikis_enqueued']}")

    elif args.cmd == "queue":
        status = kd.get_queue_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    elif args.cmd == "search-all":
        results = kd.search_all(args.query, limit=args.limit)
        if not results:
            print("Keine Treffer.")
        for r in results:
            src = r.get('source', '?')
            name = r.get('name', '?')
            typ = r.get('type', '')
            print(f"  [{src}] {name}" + (f" ({typ})" if typ else ""))
            if r.get('snippet'):
                print(f"    {r['snippet'][:120]}")
            print()

    else:
        parser.print_help()

    kd.close()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
