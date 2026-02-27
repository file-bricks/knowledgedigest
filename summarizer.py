# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- LLM Summarization via Anthropic Haiku.

Verarbeitet Chunks aus der digest_queue:
    - Pro Chunk: 3-5 Satz-Summary
    - Keyword-Extraktion
    - Domain/Topic-Klassifikation
    - Token-Tracking fuer Kosten

Usage:
    from KnowledgeDigest.summarizer import Summarizer
    s = Summarizer(knowledge_db_path)
    stats = s.summarize_queue(limit=10)
    print(stats)
"""

__all__ = ["Summarizer"]

import json
import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from .schema import ensure_schema

# Haiku Model-ID
_MODEL = "claude-haiku-4-5-20251001"

# System-Prompt fuer Summarization
_SYSTEM_PROMPT = """\
Du bist ein Wissens-Analyst. Analysiere den folgenden Textabschnitt und erstelle eine strukturierte Zusammenfassung.

Antworte AUSSCHLIESSLICH mit validem JSON in diesem Format:
{
    "summary": "3-5 Saetze die den Kerninhalt zusammenfassen",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "domain": "Hauptthema/Fachgebiet (z.B. 'Softwareentwicklung', 'Physik', 'Medizin')"
}

Regeln:
- Summary: 3-5 praegnante Saetze, keine Aufzaehlungen
- Keywords: 3-8 relevante Fachbegriffe
- Domain: Ein einzelnes Wort oder kurzer Begriff
- Sprache der Summary: gleiche Sprache wie der Input
- NUR JSON ausgeben, kein Markdown, kein Text drumherum
"""


class Summarizer:
    """LLM-basierte Chunk-Summarization via Anthropic Haiku.

    Usage:
        s = Summarizer(knowledge_db_path)
        stats = s.summarize_queue(limit=10)
    """

    def __init__(self, knowledge_db: Path, api_key: Optional[str] = None):
        self.knowledge_db = knowledge_db
        self._conn: Optional[sqlite3.Connection] = None
        self._api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self._client = None

    def _get_conn(self) -> sqlite3.Connection:
        """Lazy-init der DB-Connection."""
        if self._conn is None:
            self._conn = ensure_schema(self.knowledge_db)
        return self._conn

    def _get_client(self):
        """Lazy-init des Anthropic-Clients."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY nicht gesetzt. "
                    "Setze die Umgebungsvariable oder uebergib api_key."
                )
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def close(self):
        """Schliesst DB-Connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def summarize_queue(self, *, limit: int = 10,
                        delay: float = 0.5) -> Dict[str, Any]:
        """Verarbeitet pending Items aus der digest_queue.

        Args:
            limit: Maximale Anzahl Queue-Items
            delay: Pause zwischen API-Calls in Sekunden

        Returns:
            Statistiken ueber die Verarbeitung
        """
        start = time.time()
        conn = self._get_conn()

        stats = {
            'processed': 0,
            'errors': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'items': [],
        }

        # Pending Items holen
        queue_items = conn.execute("""
            SELECT id, source_type, source_id
            FROM digest_queue
            WHERE status = 'pending' AND step = 'summarize'
            ORDER BY created_at
            LIMIT ?
        """, (limit,)).fetchall()

        if not queue_items:
            stats['message'] = 'Keine pending Items in der Queue'
            return stats

        for item in queue_items:
            queue_id = item['id']
            source_type = item['source_type']
            source_id = item['source_id']

            # Status auf 'processing' setzen
            conn.execute(
                "UPDATE digest_queue SET status='processing', "
                "started_at=CURRENT_TIMESTAMP WHERE id=?",
                (queue_id,)
            )
            conn.commit()

            try:
                # Chunks fuer diese Quelle laden
                chunks = self._load_chunks(conn, source_type, source_id)
                if not chunks:
                    conn.execute(
                        "UPDATE digest_queue SET status='error', "
                        "error_msg='Keine Chunks gefunden', "
                        "finished_at=CURRENT_TIMESTAMP WHERE id=?",
                        (queue_id,)
                    )
                    conn.commit()
                    stats['errors'] += 1
                    continue

                # Jeden Chunk summarisieren
                item_result = {
                    'source_type': source_type,
                    'source_id': source_id,
                    'chunks_summarized': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                }

                for chunk_index, chunk_content in chunks:
                    summary_result = self._summarize_chunk(chunk_content)

                    if summary_result.get('error'):
                        continue

                    # Summary in DB speichern
                    conn.execute("""
                        INSERT INTO summaries
                            (source_type, source_id, chunk_index, summary,
                             keywords, domain, model, input_tokens, output_tokens)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_type, source_id, chunk_index)
                        DO UPDATE SET
                            summary=excluded.summary,
                            keywords=excluded.keywords,
                            domain=excluded.domain,
                            model=excluded.model,
                            input_tokens=excluded.input_tokens,
                            output_tokens=excluded.output_tokens,
                            created_at=CURRENT_TIMESTAMP
                    """, (
                        source_type, source_id, chunk_index,
                        summary_result['summary'],
                        ','.join(summary_result.get('keywords', [])),
                        summary_result.get('domain', ''),
                        _MODEL,
                        summary_result.get('input_tokens', 0),
                        summary_result.get('output_tokens', 0),
                    ))

                    item_result['chunks_summarized'] += 1
                    item_result['input_tokens'] += summary_result.get('input_tokens', 0)
                    item_result['output_tokens'] += summary_result.get('output_tokens', 0)

                    # Rate-Limiting
                    if delay > 0:
                        time.sleep(delay)

                conn.execute(
                    "UPDATE digest_queue SET status='done', "
                    "finished_at=CURRENT_TIMESTAMP WHERE id=?",
                    (queue_id,)
                )
                conn.commit()

                stats['processed'] += 1
                stats['total_input_tokens'] += item_result['input_tokens']
                stats['total_output_tokens'] += item_result['output_tokens']
                stats['items'].append(item_result)

            except Exception as e:
                conn.execute(
                    "UPDATE digest_queue SET status='error', "
                    "error_msg=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
                    (str(e)[:500], queue_id)
                )
                conn.commit()
                stats['errors'] += 1

        elapsed = int((time.time() - start) * 1000)
        stats['duration_ms'] = elapsed

        # Kosten-Schaetzung (Haiku: ~$0.25/MTok Input, ~$1.25/MTok Output)
        input_cost = stats['total_input_tokens'] / 1_000_000 * 0.25
        output_cost = stats['total_output_tokens'] / 1_000_000 * 1.25
        stats['estimated_cost_usd'] = round(input_cost + output_cost, 4)

        return stats

    def _load_chunks(self, conn: sqlite3.Connection,
                     source_type: str, source_id: int) -> List[tuple]:
        """Laedt Chunks fuer eine Quelle."""
        if source_type == 'document':
            rows = conn.execute(
                "SELECT chunk_index, content FROM document_chunks "
                "WHERE doc_id = ? ORDER BY chunk_index",
                (source_id,)
            ).fetchall()
        elif source_type == 'skill':
            rows = conn.execute(
                "SELECT chunk_index, content FROM skill_chunks "
                "WHERE skill_id = ? ORDER BY chunk_index",
                (source_id,)
            ).fetchall()
        elif source_type == 'wiki':
            rows = conn.execute(
                "SELECT chunk_index, content FROM wiki_chunks "
                "WHERE wiki_id = ? ORDER BY chunk_index",
                (source_id,)
            ).fetchall()
        else:
            return []

        return [(r['chunk_index'], r['content']) for r in rows]

    def _summarize_chunk(self, text: str) -> Dict[str, Any]:
        """Summarisiert einen einzelnen Chunk via Haiku."""
        try:
            client = self._get_client()
            response = client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
            )

            # Token-Usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Response parsen
            raw_text = response.content[0].text.strip()

            # JSON extrahieren (auch wenn in Markdown eingebettet)
            if raw_text.startswith('```'):
                lines = raw_text.split('\n')
                json_lines = [l for l in lines if not l.startswith('```')]
                raw_text = '\n'.join(json_lines)

            data = json.loads(raw_text)

            return {
                'summary': data.get('summary', ''),
                'keywords': data.get('keywords', []),
                'domain': data.get('domain', ''),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
            }

        except json.JSONDecodeError:
            # Fallback: rohen Text als Summary verwenden
            return {
                'summary': raw_text[:500] if 'raw_text' in dir() else '',
                'keywords': [],
                'domain': '',
                'input_tokens': input_tokens if 'input_tokens' in dir() else 0,
                'output_tokens': output_tokens if 'output_tokens' in dir() else 0,
            }
        except Exception as e:
            return {'error': str(e)}

    def enqueue_skills(self) -> int:
        """Erstellt Queue-Eintraege fuer alle Skills (ohne bestehende Summaries)."""
        conn = self._get_conn()
        count = 0
        rows = conn.execute(
            "SELECT id FROM skill_index WHERE chunk_count > 0"
        ).fetchall()
        for row in rows:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO digest_queue "
                    "(source_type, source_id, status, step) "
                    "VALUES ('skill', ?, 'pending', 'summarize')",
                    (row['id'],)
                )
                count += 1
            except Exception:
                pass
        conn.commit()
        return count

    def enqueue_wikis(self) -> int:
        """Erstellt Queue-Eintraege fuer alle Wikis (ohne bestehende Summaries)."""
        conn = self._get_conn()
        count = 0
        rows = conn.execute(
            "SELECT id FROM wiki_index WHERE chunk_count > 0"
        ).fetchall()
        for row in rows:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO digest_queue "
                    "(source_type, source_id, status, step) "
                    "VALUES ('wiki', ?, 'pending', 'summarize')",
                    (row['id'],)
                )
                count += 1
            except Exception:
                pass
        conn.commit()
        return count

    def get_queue_status(self) -> Dict[str, Any]:
        """Gibt Queue-Statistiken zurueck."""
        conn = self._get_conn()

        by_status = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM digest_queue
            GROUP BY status
        """).fetchall()

        by_type = conn.execute("""
            SELECT source_type, status, COUNT(*) as cnt
            FROM digest_queue
            GROUP BY source_type, status
        """).fetchall()

        total_summaries = conn.execute(
            "SELECT COUNT(*) FROM summaries"
        ).fetchone()[0]

        total_tokens_in = conn.execute(
            "SELECT SUM(input_tokens) FROM summaries"
        ).fetchone()[0] or 0

        total_tokens_out = conn.execute(
            "SELECT SUM(output_tokens) FROM summaries"
        ).fetchone()[0] or 0

        # Kosten
        input_cost = total_tokens_in / 1_000_000 * 0.25
        output_cost = total_tokens_out / 1_000_000 * 1.25

        return {
            'queue': {r['status']: r['cnt'] for r in by_status},
            'by_type': [
                {'source_type': r['source_type'],
                 'status': r['status'],
                 'count': r['cnt']}
                for r in by_type
            ],
            'summaries': {
                'total': total_summaries,
                'total_input_tokens': total_tokens_in,
                'total_output_tokens': total_tokens_out,
                'estimated_cost_usd': round(input_cost + output_cost, 4),
            },
        }
