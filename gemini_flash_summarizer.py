# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- LLM Summarization via Google Gemini 1.5 Flash.

Verarbeitet Chunks aus der digest_queue mit extremer Geschwindigkeit.

Usage:
    from KnowledgeDigest.gemini_flash_summarizer import GeminiFlashSummarizer
    s = GeminiFlashSummarizer(knowledge_db_path)
    stats = s.summarize_queue(limit=10)
"""

__all__ = ["GeminiFlashSummarizer"]

import json
import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from .schema import ensure_schema

_MODEL = "gemini-1.5-flash"

_SYSTEM_PROMPT = """\
Du bist ein Wissens-Analyst. Analysiere den folgenden Textabschnitt und erstelle eine strukturierte Zusammenfassung.

Antworte AUSSCHLIESSLICH mit validem JSON in diesem Format:
{
    "summary": "3-5 Saetze die den Kerninhalt zusammenfassen",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "domain": "Hauptthema/Fachgebiet (Ein einziges Wort, z.B. 'Softwareentwicklung', 'Physik', 'Medizin')"
}

Regeln:
- Summary: 3-5 praegnante Saetze, keine Aufzaehlungen.
- Keywords: 3-8 relevante Fachbegriffe.
- Domain: Ein einzelnes Wort oder kurzer Begriff.
- Sprache der Summary: gleiche Sprache wie der Input (i.d.R. Deutsch).
- NUR JSON ausgeben, kein Markdown wie ```json, kein Text drumherum.
"""

class GeminiFlashSummarizer:
    def __init__(self, knowledge_db: Path, api_key: Optional[str] = None):
        self.knowledge_db = knowledge_db
        self._conn: Optional[sqlite3.Connection] = None
        self._api_key = api_key or os.environ.get('GEMINI_API_KEY')
        self._client = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = ensure_schema(self.knowledge_db)
        return self._conn

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY nicht gesetzt. "
                    "Setze die Umgebungsvariable oder uebergib api_key."
                )
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def summarize_queue(self, *, limit: int = 10, delay: float = 0.5) -> Dict[str, Any]:
        start = time.time()
        conn = self._get_conn()

        stats = {
            'processed': 0,
            'errors': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'items': [],
        }

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

            conn.execute(
                "UPDATE digest_queue SET status='processing', started_at=CURRENT_TIMESTAMP WHERE id=?",
                (queue_id,)
            )
            conn.commit()

            try:
                chunks = self._load_chunks(conn, source_type, source_id)
                if not chunks:
                    conn.execute("UPDATE digest_queue SET status='error', error_msg='Keine Chunks gefunden', finished_at=CURRENT_TIMESTAMP WHERE id=?", (queue_id,))
                    conn.commit()
                    stats['errors'] += 1
                    continue

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

                    conn.execute("""
                        INSERT INTO summaries
                            (source_type, source_id, chunk_index, summary, keywords, domain, model, input_tokens, output_tokens)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_type, source_id, chunk_index) DO UPDATE SET
                            summary=excluded.summary, keywords=excluded.keywords,
                            domain=excluded.domain, model=excluded.model,
                            input_tokens=excluded.input_tokens, output_tokens=excluded.output_tokens,
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

                    if delay > 0:
                        time.sleep(delay)

                conn.execute("UPDATE digest_queue SET status='done', finished_at=CURRENT_TIMESTAMP WHERE id=?", (queue_id,))
                conn.commit()

                stats['processed'] += 1
                stats['total_input_tokens'] += item_result['input_tokens']
                stats['total_output_tokens'] += item_result['output_tokens']
                stats['items'].append(item_result)

            except Exception as e:
                conn.execute(
                    "UPDATE digest_queue SET status='error', error_msg=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
                    (str(e)[:500], queue_id)
                )
                conn.commit()
                stats['errors'] += 1

        elapsed = int((time.time() - start) * 1000)
        stats['duration_ms'] = elapsed

        # Kosten-Schaetzung Flash (sehr viel guenstiger als Haiku)
        input_cost = stats['total_input_tokens'] / 1_000_000 * 0.075
        output_cost = stats['total_output_tokens'] / 1_000_000 * 0.30
        stats['estimated_cost_usd'] = round(input_cost + output_cost, 6)

        return stats

    def _load_chunks(self, conn: sqlite3.Connection, source_type: str, source_id: int) -> List[tuple]:
        if source_type == 'document':
            rows = conn.execute("SELECT chunk_index, content FROM document_chunks WHERE doc_id = ? ORDER BY chunk_index", (source_id,)).fetchall()
        elif source_type == 'skill':
            rows = conn.execute("SELECT chunk_index, content FROM skill_chunks WHERE skill_id = ? ORDER BY chunk_index", (source_id,)).fetchall()
        elif source_type == 'wiki':
            rows = conn.execute("SELECT chunk_index, content FROM wiki_chunks WHERE wiki_id = ? ORDER BY chunk_index", (source_id,)).fetchall()
        else:
            return []
        return [(r['chunk_index'], r['content']) for r in rows]

    def _summarize_chunk(self, text: str) -> Dict[str, Any]:
        try:
            client = self._get_client()
            from google.genai import types
            
            response = client.models.generate_content(
                model=_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.3,
                    response_mime_type="application/json"
                )
            )

            # Token-Usage
            input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
            output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0

            raw_text = response.text.strip()
            
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
        except Exception as e:
            return {'error': str(e)}

