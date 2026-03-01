# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Preview Panel.
Zeigt Vorschau des ausgewaehlten Dokuments.
Adaptiert von DokuZentrum (gui/panels/preview_panel.py).
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QScrollArea,
    QStackedWidget, QPushButton, QHBoxLayout, QTabWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QImage


class PreviewPanel(QWidget):
    """Rechtes Panel: Dokumentvorschau."""

    TEXT_EXTENSIONS = {".txt", ".py", ".log", ".json", ".xml", ".md", ".csv", ".html", ".css", ".js", ".rst"}
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Optional[str] = None
        self._current_doc: Optional[dict] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        self._header_label = QLabel("<b>Vorschau</b>")
        header.addWidget(self._header_label)
        header.addStretch()

        self._btn_open = QPushButton("Datei oeffnen")
        self._btn_open.setFixedWidth(100)
        self._btn_open.clicked.connect(self._open_external)
        self._btn_open.setEnabled(False)
        header.addWidget(self._btn_open)

        layout.addLayout(header)

        # Tab-Widget fuer verschiedene Ansichten
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Tab 1: Vorschau (Text/Bild/PDF)
        self._stack = QStackedWidget()

        # Seite 0: Leer
        empty = QWidget()
        el = QVBoxLayout(empty)
        lbl = QLabel("Kein Dokument ausgewaehlt")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #8b949e;")
        el.addWidget(lbl)
        self._stack.addWidget(empty)

        # Seite 1: Text
        self._text_widget = QTextEdit()
        self._text_widget.setReadOnly(True)
        self._text_widget.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        self._stack.addWidget(self._text_widget)

        # Seite 2: Bild
        self._image_scroll = QScrollArea()
        self._image_scroll.setWidgetResizable(True)
        self._image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_scroll.setWidget(self._image_label)
        self._stack.addWidget(self._image_scroll)

        # Seite 3: Nicht unterstuetzt
        unsupported = QWidget()
        ul = QVBoxLayout(unsupported)
        self._unsupported_label = QLabel("Vorschau nicht verfuegbar")
        self._unsupported_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._unsupported_label.setStyleSheet("color: #8b949e;")
        ul.addWidget(self._unsupported_label)
        self._stack.addWidget(unsupported)

        self._tabs.addTab(self._stack, "Vorschau")

        # Tab 2: Info (Metadaten, Keywords, Summary)
        self._info_widget = QTextEdit()
        self._info_widget.setReadOnly(True)
        self._tabs.addTab(self._info_widget, "Info")

        # Tab 3: Chunks (Volltext aus DB)
        self._chunks_widget = QTextEdit()
        self._chunks_widget.setReadOnly(True)
        self._chunks_widget.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        self._tabs.addTab(self._chunks_widget, "Chunks")

    def show_document(self, doc_data):
        """Zeigt Vorschau fuer ein Dokument (dict aus DB)."""
        self._current_doc = doc_data
        file_path = doc_data.get("file_path", "")
        self._current_path = file_path

        name = doc_data.get("filename", Path(file_path).name if file_path else "?")
        self._header_label.setText(f"<b>{name}</b>")
        self._btn_open.setEnabled(bool(file_path))

        # Vorschau-Tab
        if file_path:
            p = Path(file_path)
            ext = p.suffix.lower()
            if p.exists():
                if ext in self.TEXT_EXTENSIONS:
                    self._show_text(p)
                elif ext in self.IMAGE_EXTENSIONS:
                    self._show_image(p)
                elif ext == ".pdf":
                    self._show_pdf(p)
                else:
                    self._show_unsupported(ext)
            else:
                self._unsupported_label.setText(f"Datei nicht gefunden:\n{file_path}")
                self._stack.setCurrentIndex(3)
        else:
            self._stack.setCurrentIndex(0)

        # Info-Tab
        self._show_info(doc_data)

        # Chunks-Tab
        self._show_chunks(doc_data)

    def clear(self):
        self._current_path = None
        self._current_doc = None
        self._btn_open.setEnabled(False)
        self._header_label.setText("<b>Vorschau</b>")
        self._stack.setCurrentIndex(0)
        self._info_widget.clear()
        self._chunks_widget.clear()

    def _show_text(self, path: Path):
        content = None
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    content = f.read(100000)
                break
            except UnicodeDecodeError:
                continue
        if content is None:
            self._unsupported_label.setText("Encoding nicht erkannt")
            self._stack.setCurrentIndex(3)
            return
        self._text_widget.setPlainText(content)
        self._stack.setCurrentIndex(1)

    def _show_image(self, path: Path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._unsupported_label.setText("Bild konnte nicht geladen werden")
            self._stack.setCurrentIndex(3)
            return
        max_size = QSize(800, 800)
        if pixmap.width() > max_size.width() or pixmap.height() > max_size.height():
            pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        self._image_label.setPixmap(pixmap)
        self._stack.setCurrentIndex(2)

    def _show_pdf(self, path: Path):
        try:
            import fitz
            doc = fitz.open(str(path))
            if doc.page_count > 0:
                page = doc[0]
                mat = fitz.Matrix(150/72, 150/72)
                pix = page.get_pixmap(matrix=mat)
                qimg = QImage(pix.samples, pix.width, pix.height,
                              pix.stride, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                max_size = QSize(700, 900)
                if pixmap.width() > max_size.width() or pixmap.height() > max_size.height():
                    pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                self._image_label.setPixmap(pixmap)
                self._stack.setCurrentIndex(2)
            doc.close()
        except ImportError:
            self._unsupported_label.setText(
                "PDF-Vorschau benoetigt PyMuPDF:\npip install PyMuPDF"
            )
            self._stack.setCurrentIndex(3)
        except Exception as e:
            self._unsupported_label.setText(f"PDF-Fehler:\n{e}")
            self._stack.setCurrentIndex(3)

    def _show_unsupported(self, ext):
        self._unsupported_label.setText(f"Vorschau fuer {ext.upper()} nicht verfuegbar")
        self._stack.setCurrentIndex(3)

    def _show_info(self, doc):
        """Zeigt Metadaten im Info-Tab."""
        lines = []
        lines.append(f"Dateiname: {doc.get('filename', '?')}")
        lines.append(f"Pfad: {doc.get('file_path', '?')}")
        lines.append(f"Typ: {doc.get('file_type', '?')}")
        lines.append(f"Woerter: {doc.get('word_count', '?')}")
        lines.append(f"Chunks: {doc.get('chunk_count', '?')}")
        lines.append(f"Verzeichnis: {doc.get('source_dir', '?')}")
        lines.append("")

        # Keywords und Summary aus DB laden
        doc_id = doc.get("id")
        if doc_id:
            try:
                from ..schema import ensure_schema
                conn = ensure_schema(self._current_doc_db_path())
                # Keywords
                kws = conn.execute(
                    "SELECT keyword, source FROM document_keywords WHERE doc_id=? ORDER BY keyword",
                    (doc_id,)
                ).fetchall()
                if kws:
                    lines.append("Keywords:")
                    for kw in kws:
                        lines.append(f"  - {kw['keyword']} ({kw['source']})")
                    lines.append("")

                # Summaries
                sums = conn.execute(
                    "SELECT chunk_index, summary, keywords, domain, model FROM summaries "
                    "WHERE source_type='document' AND source_id=? ORDER BY chunk_index",
                    (doc_id,)
                ).fetchall()
                if sums:
                    lines.append("Summaries:")
                    for s in sums:
                        lines.append(f"  Chunk {s['chunk_index']} [{s['domain']}] ({s['model']}):")
                        lines.append(f"    {s['summary']}")
                        if s['keywords']:
                            lines.append(f"    Keywords: {s['keywords']}")
                        lines.append("")
                conn.close()
            except Exception:
                pass

        self._info_widget.setPlainText("\n".join(lines))

    def _show_chunks(self, doc):
        """Zeigt Chunk-Content im Chunks-Tab."""
        doc_id = doc.get("id")
        if not doc_id:
            self._chunks_widget.setPlainText("Keine Chunks verfuegbar.")
            return
        try:
            from ..schema import ensure_schema
            conn = ensure_schema(self._current_doc_db_path())
            chunks = conn.execute(
                "SELECT chunk_index, content FROM document_chunks WHERE doc_id=? ORDER BY chunk_index",
                (doc_id,)
            ).fetchall()
            conn.close()

            lines = []
            for c in chunks:
                lines.append(f"=== Chunk {c['chunk_index']} ===")
                lines.append(c["content"])
                lines.append("")

            self._chunks_widget.setPlainText("\n".join(lines))
        except Exception as e:
            self._chunks_widget.setPlainText(f"Fehler: {e}")

    def _current_doc_db_path(self):
        """Gibt den DB-Pfad zurueck."""
        from ..config import get_config
        return get_config().get_db_path()

    def _open_external(self):
        if self._current_path:
            if sys.platform == "win32":
                os.startfile(self._current_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", self._current_path])
            else:
                subprocess.run(["xdg-open", self._current_path])
