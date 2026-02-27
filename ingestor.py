# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Document Ingestion Pipeline.

Verarbeitet Dateien aus einem Eingangsordner (inbox/):
    1. Dateityp erkennen
    2. Text extrahieren (PDF, DOCX, TXT, MD, HTML)
    3. Text chunken
    4. Keywords extrahieren
    5. In DB speichern (documents, document_chunks, document_keywords)
    6. Queue-Eintrag fuer LLM-Summarization erstellen
    7. Original in archive/ verschieben

Usage:
    from KnowledgeDigest.ingestor import DocumentIngestor
    ing = DocumentIngestor(knowledge_db_path)
    stats = ing.ingest_file("/path/to/document.pdf")
    stats = ing.ingest_directory("/path/to/inbox/")
"""

__all__ = ["DocumentIngestor"]

import sqlite3
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any

from .schema import ensure_schema
from .chunker import chunk_text, estimate_tokens
from .extractor import TextExtractor
from .utils import sha256_hash, extract_keywords


# Standard-Ordner relativ zum data/-Verzeichnis
_DATA_DIR = Path(__file__).parent / "data"


class DocumentIngestor:
    """Verarbeitet Dateien und speichert sie in der Wissensdatenbank.

    Usage:
        ing = DocumentIngestor(knowledge_db_path)
        result = ing.ingest_file(Path("document.pdf"))
        result = ing.ingest_directory(Path("inbox/"))
    """

    def __init__(self, knowledge_db: Path):
        self.knowledge_db = knowledge_db
        self._conn: Optional[sqlite3.Connection] = None
        self._extractor = TextExtractor()
        self.inbox_dir = _DATA_DIR / "inbox"
        self.archive_dir = _DATA_DIR / "archive"

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

    def _ensure_dirs(self):
        """Erstellt inbox/ und archive/ Ordner falls noetig."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def ingest_file(self, path: Path, *,
                    archive: bool = True,
                    chunk_size: int = 350,
                    overlap: int = 0) -> Dict[str, Any]:
        """Verarbeitet eine einzelne Datei.

        Args:
            path: Pfad zur Datei
            archive: Original nach archive/ verschieben
            chunk_size: Woerter pro Chunk
            overlap: Overlap zwischen Chunks

        Returns:
            Dict mit Ergebnis:
            {
                'status': 'ok' | 'skipped' | 'error',
                'filename': 'document.pdf',
                'chunks': 5,
                'keywords': 20,
                'words': 1234,
                'method': 'pdfplumber',
                'error': None,
            }
        """
        path = Path(path)
        result = {
            'status': 'error',
            'filename': path.name,
            'file_path': str(path),
            'chunks': 0,
            'keywords': 0,
            'words': 0,
            'method': '',
            'error': None,
        }

        # Existenz pruefen
        if not path.exists():
            result['error'] = f'Datei nicht gefunden: {path}'
            return result

        # Dateityp pruefen
        if not self._extractor.can_extract(path):
            result['error'] = f'Dateityp nicht unterstuetzt: {path.suffix}'
            result['status'] = 'skipped'
            return result

        conn = self._get_conn()

        try:
            # Text extrahieren
            extracted = self._extractor.extract(path)
            if not extracted.text.strip():
                result['error'] = f'Kein Text extrahiert ({extracted.method})'
                result['status'] = 'skipped'
                return result

            result['method'] = extracted.method

            # Duplikat-Check via content_hash
            content_hash = sha256_hash(extracted.text)
            existing = conn.execute(
                "SELECT id, file_path FROM documents WHERE content_hash = ?",
                (content_hash,)
            ).fetchone()
            if existing:
                result['status'] = 'skipped'
                result['error'] = f'Duplikat von {existing["file_path"]}'
                return result

            # Auch pruefen ob gleicher Pfad schon existiert
            existing_path = conn.execute(
                "SELECT id, content_hash FROM documents WHERE file_path = ?",
                (str(path.resolve()),)
            ).fetchone()
            if existing_path and existing_path['content_hash'] == content_hash:
                result['status'] = 'skipped'
                result['error'] = 'Bereits indexiert (unveraendert)'
                return result

            # Chunking
            chunks = chunk_text(
                extracted.text,
                chunk_size=chunk_size,
                overlap=overlap,
                separate_frontmatter=True,
            )
            word_count = estimate_tokens(extracted.text)

            # Dokument in DB speichern
            file_size = path.stat().st_size
            conn.execute("""
                INSERT INTO documents
                    (file_path, filename, file_type, file_size, content_hash,
                     language, word_count, chunk_count, page_count,
                     extraction_method, source_dir)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    filename=excluded.filename,
                    file_type=excluded.file_type,
                    file_size=excluded.file_size,
                    content_hash=excluded.content_hash,
                    language=excluded.language,
                    word_count=excluded.word_count,
                    chunk_count=excluded.chunk_count,
                    page_count=excluded.page_count,
                    extraction_method=excluded.extraction_method,
                    source_dir=excluded.source_dir,
                    ingested_at=CURRENT_TIMESTAMP
            """, (
                str(path.resolve()),
                path.name,
                path.suffix.lower().lstrip('.'),
                file_size,
                content_hash,
                extracted.language,
                word_count,
                len(chunks),
                extracted.page_count,
                extracted.method,
                str(path.parent),
            ))

            # Doc-ID holen
            doc_id = conn.execute(
                "SELECT id FROM documents WHERE file_path = ?",
                (str(path.resolve()),)
            ).fetchone()['id']

            # Alte Chunks/Keywords loeschen (fuer Re-Ingestion)
            conn.execute("DELETE FROM document_chunks WHERE doc_id = ?", (doc_id,))
            conn.execute("DELETE FROM document_keywords WHERE doc_id = ?", (doc_id,))

            # Chunks speichern
            for chunk in chunks:
                conn.execute("""
                    INSERT INTO document_chunks
                        (doc_id, chunk_index, content, token_count)
                    VALUES (?, ?, ?, ?)
                """, (doc_id, chunk.index, chunk.content, chunk.token_count))

            # Keywords extrahieren und speichern
            keywords = extract_keywords(extracted.text)
            seen = set()
            kw_count = 0
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower not in seen:
                    seen.add(kw_lower)
                    conn.execute(
                        "INSERT OR IGNORE INTO document_keywords "
                        "(doc_id, keyword, source) VALUES (?, ?, ?)",
                        (doc_id, kw_lower, 'content')
                    )
                    kw_count += 1

            # Queue-Eintrag fuer Summarization
            conn.execute("""
                INSERT OR IGNORE INTO digest_queue
                    (source_type, source_id, status, step)
                VALUES ('document', ?, 'pending', 'summarize')
            """, (doc_id,))

            conn.commit()

            # Archivieren
            archived_path = None
            if archive:
                self._ensure_dirs()
                archived_path = self._archive_file(path)
                if archived_path:
                    conn.execute(
                        "UPDATE documents SET archived_path = ? WHERE id = ?",
                        (str(archived_path), doc_id)
                    )
                    conn.commit()

            result['status'] = 'ok'
            result['chunks'] = len(chunks)
            result['keywords'] = kw_count
            result['words'] = word_count
            if archived_path:
                result['archived_to'] = str(archived_path)

        except Exception as e:
            result['error'] = str(e)
            try:
                conn.rollback()
            except Exception:
                pass

        return result

    def ingest_directory(self, path: Optional[Path] = None, *,
                         archive: bool = True,
                         chunk_size: int = 350,
                         overlap: int = 0,
                         recursive: bool = False) -> Dict[str, Any]:
        """Verarbeitet alle unterstuetzten Dateien in einem Ordner.

        Args:
            path: Ordner-Pfad (Default: data/inbox/)
            archive: Originale nach archive/ verschieben
            chunk_size: Woerter pro Chunk
            overlap: Overlap zwischen Chunks
            recursive: Auch Unterordner durchsuchen

        Returns:
            Dict mit Gesamtstatistiken
        """
        start = time.time()
        target = Path(path) if path else self.inbox_dir
        self._ensure_dirs()

        if not target.exists():
            return {'error': f'Ordner nicht gefunden: {target}'}

        if not target.is_dir():
            return {'error': f'Kein Ordner: {target}'}

        stats = {
            'directory': str(target),
            'total_files': 0,
            'ingested': 0,
            'skipped': 0,
            'errors': 0,
            'total_chunks': 0,
            'total_keywords': 0,
            'total_words': 0,
            'files': [],
        }

        # Dateien sammeln
        if recursive:
            files = sorted(target.rglob('*'))
        else:
            files = sorted(target.iterdir())

        files = [f for f in files if f.is_file()]
        stats['total_files'] = len(files)

        for file_path in files:
            result = self.ingest_file(
                file_path,
                archive=archive,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            if result['status'] == 'ok':
                stats['ingested'] += 1
                stats['total_chunks'] += result['chunks']
                stats['total_keywords'] += result['keywords']
                stats['total_words'] += result['words']
            elif result['status'] == 'skipped':
                stats['skipped'] += 1
            else:
                stats['errors'] += 1

            stats['files'].append(result)

        stats['duration_ms'] = int((time.time() - start) * 1000)
        return stats

    def _archive_file(self, path: Path) -> Optional[Path]:
        """Verschiebt Datei nach archive/ mit Timestamp-Prefix."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = self.archive_dir / f"{timestamp}_{path.name}"

            # Bei Namenskollision: Nummer anhaengen
            counter = 1
            while dest.exists():
                dest = self.archive_dir / f"{timestamp}_{counter}_{path.name}"
                counter += 1

            shutil.move(str(path), str(dest))
            return dest
        except Exception:
            return None

    def get_ingest_status(self) -> Dict[str, Any]:
        """Gibt Ingestion-Statistiken zurueck."""
        conn = self._get_conn()

        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        total_chunks = conn.execute(
            "SELECT COUNT(*) FROM document_chunks"
        ).fetchone()[0]
        total_keywords = conn.execute(
            "SELECT COUNT(DISTINCT keyword) FROM document_keywords"
        ).fetchone()[0]
        total_words = conn.execute(
            "SELECT SUM(word_count) FROM documents"
        ).fetchone()[0] or 0

        by_type = conn.execute("""
            SELECT file_type, COUNT(*) as cnt
            FROM documents
            GROUP BY file_type
            ORDER BY cnt DESC
        """).fetchall()

        queue_pending = conn.execute(
            "SELECT COUNT(*) FROM digest_queue "
            "WHERE source_type='document' AND status='pending'"
        ).fetchone()[0]

        queue_done = conn.execute(
            "SELECT COUNT(*) FROM digest_queue "
            "WHERE source_type='document' AND status='done'"
        ).fetchone()[0]

        return {
            'total_documents': total,
            'total_chunks': total_chunks,
            'total_keywords': total_keywords,
            'total_words': total_words,
            'by_type': {r['file_type']: r['cnt'] for r in by_type},
            'queue_pending': queue_pending,
            'queue_done': queue_done,
        }
