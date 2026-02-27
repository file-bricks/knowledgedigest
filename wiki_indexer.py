# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Wiki-Indexierungslogik.

Liest Wiki-Artikel aus bach.db (read-only), chunked den Content
und speichert alles in der eigenen knowledge.db.

Workflow:
    1. bach.db oeffnen (read-only)
    2. Alle Wiki-Artikel lesen (413 Eintraege)
    3. Content chunken (via chunker.py)
    4. Keywords extrahieren
    5. In knowledge.db speichern (wiki_index + wiki_chunks + wiki_keywords)
    6. FTS5-Index wird automatisch via Trigger befuellt
"""

__all__ = ["WikiIndexer"]

import sqlite3
from pathlib import Path
from typing import Dict, Optional, Any

from .schema import ensure_schema
from .chunker import chunk_text, estimate_tokens
from .utils import sha256_hash as _sha256, extract_keywords as _extract_keywords


class WikiIndexer:
    """Indexiert BACH Wiki-Artikel in der eigenen knowledge.db.

    Usage:
        indexer = WikiIndexer(knowledge_db_path)
        result = indexer.index_from_bach(bach_db_path)
        print(result)
    """

    def __init__(self, knowledge_db: Path):
        self.knowledge_db = knowledge_db
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """Lazy-init der DB-Connection mit Schema-Sicherstellung."""
        if self._conn is None:
            self._conn = ensure_schema(self.knowledge_db)
        return self._conn

    def close(self):
        """Schliesst DB-Connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def index_from_bach(self, bach_db_path: Path, *,
                        chunk_size: int = 350,
                        overlap: int = 0,
                        force: bool = False) -> Dict[str, Any]:
        """Indexiert alle Wiki-Artikel aus bach.db.

        Args:
            bach_db_path: Pfad zur bach.db
            chunk_size: Woerter pro Chunk (Default: 350)
            overlap: Overlap zwischen Chunks in Woertern
            force: Wenn True, bestehenden Index komplett neu aufbauen

        Returns:
            Dict mit Statistiken:
            {
                'total_wikis': 413,
                'indexed': 413,
                'skipped': 0,
                'chunks_created': 1234,
                'keywords_extracted': 5678,
                'duration_ms': 1234,
            }
        """
        import time
        start = time.time()

        if not bach_db_path.exists():
            return {'error': f'bach.db nicht gefunden: {bach_db_path}'}

        conn = self._get_conn()

        # Bei force: alles loeschen
        if force:
            conn.execute("DELETE FROM wiki_keywords")
            conn.execute("DELETE FROM wiki_chunks")
            conn.execute("DELETE FROM wiki_index")
            conn.commit()

        # bach.db read-only oeffnen
        bach_conn = sqlite3.connect(f'file:{bach_db_path}?mode=ro', uri=True)
        bach_conn.row_factory = sqlite3.Row

        stats = {
            'total_wikis': 0,
            'indexed': 0,
            'skipped': 0,
            'unchanged': 0,
            'chunks_created': 0,
            'keywords_extracted': 0,
        }

        try:
            rows = bach_conn.execute("""
                SELECT path, title, content, category, last_modified, tags
                FROM wiki_articles
            """).fetchall()

            stats['total_wikis'] = len(rows)

            for row in rows:
                wiki_path = row['path']
                content = row['content'] or ''
                content_hash = _sha256(content) if content else ''

                # Skip wenn kein Content
                if not content.strip():
                    stats['skipped'] += 1
                    continue

                # Pruefen ob bereits indexiert mit gleichem Hash
                if not force:
                    existing = conn.execute(
                        "SELECT id, content_hash FROM wiki_index WHERE wiki_path = ?",
                        (wiki_path,)
                    ).fetchone()
                    if existing and existing['content_hash'] == content_hash:
                        stats['unchanged'] += 1
                        continue

                # Wiki-Metadaten speichern
                word_count = estimate_tokens(content)
                chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
                chunk_count = len(chunks)

                conn.execute("""
                    INSERT INTO wiki_index
                        (wiki_path, title, category, tags, content_hash,
                         word_count, chunk_count, last_modified, source_db)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(wiki_path) DO UPDATE SET
                        title=excluded.title,
                        category=excluded.category,
                        tags=excluded.tags,
                        content_hash=excluded.content_hash,
                        word_count=excluded.word_count,
                        chunk_count=excluded.chunk_count,
                        last_modified=excluded.last_modified,
                        source_db=excluded.source_db,
                        indexed_at=CURRENT_TIMESTAMP
                """, (
                    wiki_path, row['title'], row['category'], row['tags'],
                    content_hash, word_count, chunk_count,
                    row['last_modified'], str(bach_db_path),
                ))

                # Wiki-ID holen
                wiki_id = conn.execute(
                    "SELECT id FROM wiki_index WHERE wiki_path = ?",
                    (wiki_path,)
                ).fetchone()['id']

                # Alte Chunks/Keywords loeschen (fuer Updates)
                conn.execute("DELETE FROM wiki_chunks WHERE wiki_id = ?", (wiki_id,))
                conn.execute("DELETE FROM wiki_keywords WHERE wiki_id = ?", (wiki_id,))

                # Chunks speichern
                for chunk in chunks:
                    conn.execute("""
                        INSERT INTO wiki_chunks
                            (wiki_id, chunk_index, content, token_count)
                        VALUES (?, ?, ?, ?)
                    """, (
                        wiki_id, chunk.index, chunk.content, chunk.token_count,
                    ))
                    stats['chunks_created'] += 1

                # Keywords extrahieren und speichern
                keywords = _extract_keywords(content)

                # Zusaetzliche Keywords aus Metadaten
                if row['category']:
                    keywords.append(row['category'])
                if row['tags']:
                    # Tags sind kommasepariert
                    tag_list = [t.strip() for t in row['tags'].split(',') if t.strip()]
                    keywords.extend(tag_list)

                # Deduplizieren
                seen = set()
                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower not in seen:
                        seen.add(kw_lower)
                        source = 'metadata' if kw in ([row['category']] + (row['tags'] or '').split(',')) else 'content'
                        conn.execute(
                            "INSERT OR IGNORE INTO wiki_keywords (wiki_id, keyword, source) "
                            "VALUES (?, ?, ?)",
                            (wiki_id, kw_lower, source)
                        )
                        stats['keywords_extracted'] += 1

                stats['indexed'] += 1

                # Periodisch committen
                if stats['indexed'] % 50 == 0:
                    conn.commit()

            conn.commit()

        finally:
            bach_conn.close()

        elapsed = int((time.time() - start) * 1000)
        stats['duration_ms'] = elapsed
        return stats

    def get_index_status(self) -> Dict[str, Any]:
        """Gibt Indexierungs-Statistiken zurueck."""
        conn = self._get_conn()

        total = conn.execute("SELECT COUNT(*) FROM wiki_index").fetchone()[0]
        total_chunks = conn.execute("SELECT COUNT(*) FROM wiki_chunks").fetchone()[0]
        total_keywords = conn.execute("SELECT COUNT(DISTINCT keyword) FROM wiki_keywords").fetchone()[0]

        by_category = conn.execute("""
            SELECT category, COUNT(*) as cnt
            FROM wiki_index
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY cnt DESC
            LIMIT 20
        """).fetchall()

        total_words = conn.execute(
            "SELECT SUM(word_count) FROM wiki_index"
        ).fetchone()[0] or 0

        avg_chunks = conn.execute(
            "SELECT AVG(chunk_count) FROM wiki_index WHERE chunk_count > 0"
        ).fetchone()[0] or 0

        return {
            'total_wikis': total,
            'total_chunks': total_chunks,
            'total_keywords': total_keywords,
            'total_words': total_words,
            'avg_chunks_per_wiki': round(avg_chunks, 1),
            'by_category': {r['category']: r['cnt'] for r in by_category},
        }
