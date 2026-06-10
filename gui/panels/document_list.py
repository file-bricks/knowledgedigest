# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Document List Panel.
Zeigt Dokumente als sortierbare Tabelle.
Adaptiert von DokuZentrum (gui/panels/document_list.py).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt

from ..event_bus import EventType, get_event_bus


class DocumentListPanel(QWidget):
    """Mittleres Panel: Dokumentenliste."""

    COLUMNS = ["Dateiname", "Typ", "Woerter", "Chunks", "Status"]

    def __init__(self, kd, parent=None):
        super().__init__(parent)
        self._kd = kd
        self._bus = get_event_bus()
        self._current_filter = None
        self._docs = []
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table)

    def _connect_signals(self):
        self._table.currentCellChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(self._on_double_click)

    def refresh(self):
        """Laedt Dokumentenliste aus der DB."""
        self._load_documents(self._current_filter)

    def filter_by_directory(self, path):
        """Filtert nach Verzeichnis."""
        if path == "__all__":
            self._current_filter = None
        else:
            self._current_filter = path
        self._load_documents(self._current_filter)

    def show_search_results(self, results):
        """Zeigt Suchergebnisse."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._docs = []

        for r in results:
            self._docs.append(r)
            row = self._table.rowCount()
            self._table.insertRow(row)

            name = r.get("filename", r.get("name", "?"))
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(r.get("file_type", r.get("source", ""))))

            wc = QTableWidgetItem()
            wc.setData(Qt.ItemDataRole.DisplayRole, r.get("word_count", 0))
            self._table.setItem(row, 2, wc)

            cc = QTableWidgetItem()
            cc.setData(Qt.ItemDataRole.DisplayRole, r.get("chunk_count", 0))
            self._table.setItem(row, 3, cc)

            self._table.setItem(row, 4, QTableWidgetItem(
                r.get("snippet", "")[:60] if r.get("snippet") else ""
            ))

        self._table.setSortingEnabled(True)
        self._bus.emit(EventType.STATUS_MESSAGE, f"{len(results)} Suchergebnisse")

    def _load_documents(self, dir_filter=None):
        """Laedt Dokumente aus der DB."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._docs = []

        try:
            from ..config import get_config
            from ..schema import ensure_schema
            conn = ensure_schema(self._kd.db_path)

            if dir_filter:
                rows = conn.execute("""
                    SELECT d.id, d.filename, d.file_type, d.word_count, d.chunk_count,
                           d.file_path, d.source_dir,
                           (SELECT COUNT(*) FROM summaries s
                            WHERE s.source_type='document' AND s.source_id=d.id) as sum_count
                    FROM documents d
                    WHERE d.source_dir LIKE ?
                    ORDER BY d.filename
                """, (dir_filter + "%",)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT d.id, d.filename, d.file_type, d.word_count, d.chunk_count,
                           d.file_path, d.source_dir,
                           (SELECT COUNT(*) FROM summaries s
                            WHERE s.source_type='document' AND s.source_id=d.id) as sum_count
                    FROM documents d
                    ORDER BY d.filename
                """).fetchall()

            conn.close()

            for row in rows:
                doc = dict(row)
                self._docs.append(doc)
                r = self._table.rowCount()
                self._table.insertRow(r)

                self._table.setItem(r, 0, QTableWidgetItem(doc["filename"]))
                self._table.setItem(r, 1, QTableWidgetItem(doc.get("file_type", "")))

                wc = QTableWidgetItem()
                wc.setData(Qt.ItemDataRole.DisplayRole, doc.get("word_count", 0))
                self._table.setItem(r, 2, wc)

                cc = QTableWidgetItem()
                cc.setData(Qt.ItemDataRole.DisplayRole, doc.get("chunk_count", 0))
                self._table.setItem(r, 3, cc)

                sc = doc.get("sum_count", 0)
                status = "summarized" if sc > 0 else "pending"
                self._table.setItem(r, 4, QTableWidgetItem(status))

        except Exception as e:
            self._bus.emit(EventType.ERROR_MESSAGE, f"Fehler: {e}")

        self._table.setSortingEnabled(True)

    def _on_selection_changed(self, row, col, prev_row, prev_col):
        if 0 <= row < len(self._docs):
            doc = self._docs[row]
            self._bus.emit(EventType.DOCUMENT_SELECTED, doc)

    def _on_double_click(self, row, col):
        """Doppelklick oeffnet Datei."""
        if 0 <= row < len(self._docs):
            doc = self._docs[row]
            file_path = doc.get("file_path", "")
            if file_path:
                import os
                try:
                    os.startfile(file_path)
                except Exception:
                    pass
