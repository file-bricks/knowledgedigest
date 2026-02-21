# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Indexierungslogik.

Liest Skills aus bach.db (read-only), chunked den Content
und speichert alles in der eigenen knowledge.db.

Workflow:
    1. bach.db oeffnen (read-only)
    2. Alle Skills lesen (935 Eintraege)
    3. Content chunken (via chunker.py)
    4. Keywords extrahieren
    5. In knowledge.db speichern (skill_index + skill_chunks + skill_keywords)
    6. FTS5-Index wird automatisch via Trigger befuellt
"""

__all__ = ["SkillIndexer"]

import sqlite3
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from .schema import ensure_schema
from .chunker import chunk_text, estimate_tokens


# Stoppwoerter (DE/EN gemischt, fuer Keyword-Extraktion)
_STOP_WORDS = frozenset({
    # Deutsch
    'der', 'die', 'das', 'ein', 'eine', 'und', 'oder', 'aber', 'ist', 'sind',
    'wird', 'werden', 'hat', 'haben', 'mit', 'von', 'auf', 'fuer', 'zur',
    'zum', 'den', 'dem', 'des', 'als', 'auch', 'nicht', 'nur', 'wenn',
    'bei', 'aus', 'nach', 'ueber', 'unter', 'vor', 'durch', 'wie', 'noch',
    'kann', 'soll', 'muss', 'alle', 'diese', 'dieser', 'dieses', 'sich',
    'dann', 'denn', 'was', 'wer', 'wo', 'hier', 'dort', 'sein', 'seine',
    'seinem', 'seinen', 'seiner', 'einer', 'eines', 'einem', 'einen',
    # Englisch
    'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
    'can', 'not', 'no', 'nor', 'so', 'if', 'for', 'of', 'in', 'on', 'at',
    'to', 'from', 'by', 'with', 'as', 'into', 'it', 'its', 'this', 'that',
    'these', 'those', 'which', 'what', 'who', 'how', 'all', 'each', 'any',
    # YAML/Code
    'true', 'false', 'null', 'none', 'yes', 'default', 'type', 'name',
    'value', 'version', 'status', 'active', 'description',
})

# Minimum-Wortlaenge fuer Keywords
_MIN_KEYWORD_LEN = 3
_MAX_KEYWORDS_PER_SKILL = 30


def _sha256(text: str) -> str:
    """SHA256-Hash eines Textes."""
    return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()


def _extract_keywords(text: str, max_count: int = _MAX_KEYWORDS_PER_SKILL) -> List[str]:
    """Extrahiert relevante Keywords aus Text.

    Strategie:
        - Alle Woerter tokenisieren
        - Stoppwoerter und zu kurze Woerter filtern
        - Nach Haeufigkeit sortieren
        - Top-N zurueckgeben
    """
    if not text:
        return []

    # Woerter extrahieren (alphanumerisch + Umlaute + Bindestriche)
    words = re.findall(r'[a-zA-Z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df_-]{3,}', text.lower())

    # Stoppwoerter filtern
    words = [w for w in words if w not in _STOP_WORDS and len(w) >= _MIN_KEYWORD_LEN]

    # Haeufigkeit zaehlen
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    # Nach Haeufigkeit sortieren, Top-N
    sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_kw[:max_count]]


class SkillIndexer:
    """Indexiert BACH-Skills in der eigenen knowledge.db.

    Usage:
        indexer = SkillIndexer(knowledge_db_path)
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
        """Indexiert alle Skills aus bach.db.

        Args:
            bach_db_path: Pfad zur bach.db
            chunk_size: Woerter pro Chunk (Default: 350)
            overlap: Overlap zwischen Chunks in Woertern
            force: Wenn True, bestehenden Index komplett neu aufbauen

        Returns:
            Dict mit Statistiken:
            {
                'total_skills': 935,
                'indexed': 766,    # mit Content
                'skipped': 169,    # ohne Content
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
            conn.execute("DELETE FROM skill_keywords")
            conn.execute("DELETE FROM skill_chunks")
            conn.execute("DELETE FROM skill_index")
            conn.commit()

        # bach.db read-only oeffnen
        bach_conn = sqlite3.connect(f'file:{bach_db_path}?mode=ro', uri=True)
        bach_conn.row_factory = sqlite3.Row

        stats = {
            'total_skills': 0,
            'indexed': 0,
            'skipped': 0,
            'unchanged': 0,
            'chunks_created': 0,
            'keywords_extracted': 0,
        }

        try:
            rows = bach_conn.execute("""
                SELECT id, name, type, category, path, description,
                       version, content, content_hash, is_active
                FROM skills
            """).fetchall()

            stats['total_skills'] = len(rows)

            for row in rows:
                skill_name = row['name']
                content = row['content'] or ''
                content_hash = row['content_hash'] or _sha256(content) if content else ''

                # Skip wenn kein Content
                if not content.strip():
                    stats['skipped'] += 1
                    continue

                # Pruefen ob bereits indexiert mit gleichem Hash
                if not force:
                    existing = conn.execute(
                        "SELECT id, content_hash FROM skill_index WHERE skill_name = ?",
                        (skill_name,)
                    ).fetchone()
                    if existing and existing['content_hash'] == content_hash:
                        stats['unchanged'] += 1
                        continue

                # Skill-Metadaten speichern
                word_count = estimate_tokens(content)
                chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
                chunk_count = len(chunks)

                conn.execute("""
                    INSERT INTO skill_index
                        (skill_name, skill_type, category, path, description,
                         version, content_hash, word_count, chunk_count,
                         is_active, source_db)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(skill_name) DO UPDATE SET
                        skill_type=excluded.skill_type,
                        category=excluded.category,
                        path=excluded.path,
                        description=excluded.description,
                        version=excluded.version,
                        content_hash=excluded.content_hash,
                        word_count=excluded.word_count,
                        chunk_count=excluded.chunk_count,
                        is_active=excluded.is_active,
                        source_db=excluded.source_db,
                        indexed_at=CURRENT_TIMESTAMP
                """, (
                    skill_name, row['type'], row['category'], row['path'],
                    row['description'], row['version'], content_hash,
                    word_count, chunk_count, row['is_active'] or 1,
                    str(bach_db_path),
                ))

                # Skill-ID holen
                skill_id = conn.execute(
                    "SELECT id FROM skill_index WHERE skill_name = ?",
                    (skill_name,)
                ).fetchone()['id']

                # Alte Chunks/Keywords loeschen (fuer Updates)
                conn.execute("DELETE FROM skill_chunks WHERE skill_id = ?", (skill_id,))
                conn.execute("DELETE FROM skill_keywords WHERE skill_id = ?", (skill_id,))

                # Chunks speichern
                for chunk in chunks:
                    conn.execute("""
                        INSERT INTO skill_chunks
                            (skill_id, chunk_index, content, token_count, is_frontmatter)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        skill_id, chunk.index, chunk.content,
                        chunk.token_count, 1 if chunk.is_frontmatter else 0,
                    ))
                    stats['chunks_created'] += 1

                # Keywords extrahieren und speichern
                keywords = _extract_keywords(content)

                # Zusaetzliche Keywords aus Metadaten
                if row['category']:
                    keywords.append(row['category'])
                if row['type']:
                    keywords.append(row['type'])

                # Deduplizieren
                seen = set()
                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower not in seen:
                        seen.add(kw_lower)
                        source = 'metadata' if kw in (row['category'], row['type']) else 'content'
                        conn.execute(
                            "INSERT OR IGNORE INTO skill_keywords (skill_id, keyword, source) "
                            "VALUES (?, ?, ?)",
                            (skill_id, kw_lower, source)
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

        total = conn.execute("SELECT COUNT(*) FROM skill_index").fetchone()[0]
        total_chunks = conn.execute("SELECT COUNT(*) FROM skill_chunks").fetchone()[0]
        total_keywords = conn.execute("SELECT COUNT(DISTINCT keyword) FROM skill_keywords").fetchone()[0]

        by_type = conn.execute("""
            SELECT skill_type, COUNT(*) as cnt
            FROM skill_index
            GROUP BY skill_type
            ORDER BY cnt DESC
        """).fetchall()

        by_category = conn.execute("""
            SELECT category, COUNT(*) as cnt
            FROM skill_index
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY cnt DESC
            LIMIT 20
        """).fetchall()

        total_words = conn.execute(
            "SELECT SUM(word_count) FROM skill_index"
        ).fetchone()[0] or 0

        avg_chunks = conn.execute(
            "SELECT AVG(chunk_count) FROM skill_index WHERE chunk_count > 0"
        ).fetchone()[0] or 0

        return {
            'total_skills': total,
            'total_chunks': total_chunks,
            'total_keywords': total_keywords,
            'total_words': total_words,
            'avg_chunks_per_skill': round(avg_chunks, 1),
            'by_type': {r['skill_type']: r['cnt'] for r in by_type},
            'by_category': {r['category']: r['cnt'] for r in by_category},
        }
