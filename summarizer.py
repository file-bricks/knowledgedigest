# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- LLM Summarization (Provider-Agnostic).

Verarbeitet Chunks aus der digest_queue:
    - Pro Chunk: 3-5 Satz-Summary
    - Keyword-Extraktion
    - Domain/Topic-Klassifikation
    - Token-Tracking fuer Kosten

Unterstuetzte Provider:
    - anthropic: Claude Haiku (Default, benoetigt anthropic-Paket + API-Key)
    - ollama: Lokales LLM via Ollama REST API (zero-dep, kostenlos)
    - custom: Eigene Callback-Funktion

Usage:
    # Anthropic (Default)
    s = Summarizer(knowledge_db_path, provider="anthropic")

    # Ollama (lokal)
    s = Summarizer(knowledge_db_path, provider="ollama",
                   model="qwen3:4b", base_url="http://localhost:11434")

    # Custom Provider
    s = Summarizer(knowledge_db_path, provider="custom",
                   llm_fn=my_llm_function)

    stats = s.summarize_queue(limit=10)

Author: Lukas Geiger
License: MIT
"""

__all__ = ["Summarizer"]

import json
import os
import re
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from .schema import ensure_schema

# System-Prompt fuer Summarization
_SYSTEM_PROMPT = """\
Du arbeitest in KnowledgeDigest, einer Wissensdatenbank. Deine einzige Aufgabe: Textabschnitte auf ihre Kernfakten reduzieren.

Du bekommst einen Textabschnitt (Chunk) aus einem Dokument. Extrahiere die wichtigsten Fakten und gib NUR dieses JSON zurueck:

{"summary": "3-5 Saetze mit den Kernfakten", "keywords": ["fachbegriff1", "fachbegriff2"], "domain": "Fachgebiet"}

Keine Erklaerungen, kein Markdown, kein Drumherum. Nur das JSON.
"""

# Default Models per Provider
_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "ollama": "qwen3:4b",
}


class Summarizer:
    """LLM-basierte Chunk-Summarization (Provider-agnostisch).

    Provider:
        "anthropic" -- Claude Haiku via Anthropic SDK (pip install anthropic)
        "ollama"    -- Lokales LLM via Ollama REST API (zero-dep)
        "custom"    -- Eigene Funktion: fn(system_prompt, user_text) -> str
    """

    def __init__(
        self,
        knowledge_db: Path,
        provider: str = "anthropic",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:11434",
        llm_fn: Optional[Callable[[str, str], str]] = None,
        system_prompt: Optional[str] = None,
    ):
        self.knowledge_db = knowledge_db
        self.provider = provider
        self.model = model or _DEFAULT_MODELS.get(provider, "")
        self.base_url = base_url.rstrip("/")
        self.system_prompt = system_prompt or _SYSTEM_PROMPT
        self._conn: Optional[sqlite3.Connection] = None

        # Provider-spezifisch
        if provider == "anthropic":
            self._api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
            self._client = None
        elif provider == "custom":
            if not llm_fn:
                raise ValueError("provider='custom' braucht llm_fn parameter")
            self._llm_fn = llm_fn
        # ollama braucht keine Extra-Init

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = ensure_schema(self.knowledge_db)
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # === Provider Backends ===

    def _call_anthropic(self, text: str) -> Dict[str, Any]:
        """Summarisiert via Anthropic API."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY nicht gesetzt. "
                    "Setze die Umgebungsvariable oder uebergib api_key."
                )
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)

        response = self._client.messages.create(
            model=self.model,
            max_tokens=512,
            system=self.system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        return {
            "text": response.content[0].text.strip(),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    def _call_ollama(self, text: str) -> Dict[str, Any]:
        """Summarisiert via Ollama REST API (zero-dep)."""
        payload = {
            "model": self.model,
            "prompt": f"/no_think\n{text}" if "qwen" in self.model.lower() else text,
            "system": self.system_prompt,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        response_text = result.get("response", "")
        # Thinking-Tags entfernen
        if "<think>" in response_text:
            response_text = re.sub(
                r"<think>.*?</think>\s*", "", response_text, flags=re.DOTALL
            ).strip()

        return {
            "text": response_text,
            "input_tokens": result.get("prompt_eval_count", 0),
            "output_tokens": result.get("eval_count", 0),
        }

    def _call_custom(self, text: str) -> Dict[str, Any]:
        """Summarisiert via benutzerdefinierte Funktion."""
        result_text = self._llm_fn(self.system_prompt, text)
        return {
            "text": result_text,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _call_llm(self, text: str) -> Dict[str, Any]:
        """Dispatcht an den konfigurierten Provider."""
        if self.provider == "anthropic":
            return self._call_anthropic(text)
        elif self.provider == "ollama":
            return self._call_ollama(text)
        elif self.provider == "custom":
            return self._call_custom(text)
        else:
            raise ValueError(f"Unbekannter Provider: {self.provider}")

    # === Core Logic ===

    def summarize_queue(self, *, limit: int = 10,
                        delay: float = 0.5) -> Dict[str, Any]:
        """Verarbeitet pending Items aus der digest_queue."""
        start = time.time()
        conn = self._get_conn()

        stats = {
            'processed': 0,
            'errors': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'provider': self.provider,
            'model': self.model,
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
                "UPDATE digest_queue SET status='processing', "
                "started_at=CURRENT_TIMESTAMP WHERE id=?",
                (queue_id,)
            )
            conn.commit()

            try:
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
                        self.model,
                        summary_result.get('input_tokens', 0),
                        summary_result.get('output_tokens', 0),
                    ))

                    item_result['chunks_summarized'] += 1
                    item_result['input_tokens'] += summary_result.get('input_tokens', 0)
                    item_result['output_tokens'] += summary_result.get('output_tokens', 0)

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

        if self.provider == "anthropic":
            input_cost = stats['total_input_tokens'] / 1_000_000 * 0.25
            output_cost = stats['total_output_tokens'] / 1_000_000 * 1.25
            stats['estimated_cost_usd'] = round(input_cost + output_cost, 4)

        return stats

    def _load_chunks(self, conn: sqlite3.Connection,
                     source_type: str, source_id: int) -> List[tuple]:
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
        """Summarisiert einen einzelnen Chunk via konfiguriertem Provider."""
        try:
            llm_result = self._call_llm(text)
            raw_text = llm_result["text"]

            # JSON extrahieren (auch wenn in Markdown eingebettet)
            if raw_text.startswith('```'):
                lines = raw_text.split('\n')
                json_lines = [l for l in lines if not l.startswith('```')]
                raw_text = '\n'.join(json_lines)

            # JSON-Block aus Text extrahieren falls noetig
            json_match = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
            if json_match:
                raw_text = json_match.group()

            data = json.loads(raw_text)

            return {
                'summary': data.get('summary', ''),
                'keywords': data.get('keywords', []),
                'domain': data.get('domain', ''),
                'input_tokens': llm_result.get('input_tokens', 0),
                'output_tokens': llm_result.get('output_tokens', 0),
            }

        except json.JSONDecodeError:
            # Fallback: rohen Text als Summary verwenden
            return {
                'summary': llm_result.get('text', '')[:500],
                'keywords': [],
                'domain': '',
                'input_tokens': llm_result.get('input_tokens', 0),
                'output_tokens': llm_result.get('output_tokens', 0),
            }
        except Exception as e:
            return {'error': str(e)}

    # === Queue Management ===

    def enqueue_skills(self) -> int:
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

        result = {
            'provider': self.provider,
            'model': self.model,
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
            },
        }

        if self.provider == "anthropic":
            input_cost = total_tokens_in / 1_000_000 * 0.25
            output_cost = total_tokens_out / 1_000_000 * 1.25
            result['summaries']['estimated_cost_usd'] = round(
                input_cost + output_cost, 4
            )

        return result
