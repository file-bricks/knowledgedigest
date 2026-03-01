# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Ingest Progress Dialog.
Zeigt Fortschritt beim Indexieren.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QProgressBar, QLabel,
    QDialogButtonBox, QTextEdit
)
from PyQt6.QtCore import QThread, pyqtSignal


class IngestWorker(QThread):
    """Worker-Thread fuer Dokument-Ingestion."""
    progress = pyqtSignal(int, str)  # count, filename
    finished = pyqtSignal(dict)      # result stats
    error = pyqtSignal(str)

    def __init__(self, kd, path, recursive=True, archive=False, chunk_size=350):
        super().__init__()
        self._kd = kd
        self._path = path
        self._recursive = recursive
        self._archive = archive
        self._chunk_size = chunk_size

    def run(self):
        try:
            result = self._kd.scan_directory(
                self._path,
                recursive=self._recursive,
                archive=self._archive,
                chunk_size=self._chunk_size
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class IngestDialog(QDialog):
    """Dialog mit Fortschrittsanzeige fuer Ingestion."""

    def __init__(self, kd, path, parent=None):
        super().__init__(parent)
        self._kd = kd
        self._path = path
        self.setWindowTitle(f"Indexiere: {path}")
        self.setMinimumSize(400, 300)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._label = QLabel(f"Verarbeite Verzeichnis:\n{self._path}")
        layout.addWidget(self._label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._buttons.rejected.connect(self.reject)
        self._buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(False)
        layout.addWidget(self._buttons)

    def start(self):
        """Startet den Ingest-Worker."""
        self._worker = IngestWorker(self._kd, self._path)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, result):
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(True)

        ingested = result.get("ingested", 0)
        skipped = result.get("skipped", 0)
        errors = result.get("errors", 0)
        chunks = result.get("total_chunks", 0)

        self._label.setText("Fertig!")
        self._log.append(f"Verarbeitet: {ingested}")
        self._log.append(f"Uebersprungen: {skipped}")
        self._log.append(f"Fehler: {errors}")
        self._log.append(f"Chunks erstellt: {chunks}")

        if result.get("files"):
            self._log.append("\nDetails:")
            for f in result["files"]:
                status = f.get("status", "?")
                name = f.get("filename", "?")
                self._log.append(f"  [{status}] {name}")

    def _on_error(self, msg):
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(True)
        self._label.setText("Fehler!")
        self._log.append(f"FEHLER: {msg}")
