# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Main Window.
3-Panel Splitter Layout: Verzeichnisse | Dokumente | Vorschau.
Adaptiert von LitZentrum (main_window.py) + DokuZentrum (main_window.py).
"""

import os
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QLabel
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction

from .event_bus import EventBus, EventType, get_event_bus
from .panels.directory_panel import DirectoryPanel
from .panels.document_list import DocumentListPanel
from .panels.preview_panel import PreviewPanel
from .widgets.search_bar import SearchBar

from ..config import get_config
from ..digest import KnowledgeDigest


class MainWindow(QMainWindow):
    """Hauptfenster mit 3-Panel-Splitter."""

    def __init__(self):
        super().__init__()
        self._config = get_config()
        self._kd = KnowledgeDigest(config=self._config)
        self._bus = get_event_bus()
        self._web_server = None

        self.setWindowTitle("KnowledgeDigest")
        self.setMinimumSize(900, 600)

        self._setup_menubar()
        self._setup_toolbar()
        self._setup_panels()
        self._setup_statusbar()
        self._connect_events()
        self._restore_state()
        self._update_status()

    def _setup_menubar(self):
        """Erstellt die Menuleiste."""
        mb = self.menuBar()

        # Datei
        file_menu = mb.addMenu("&Datei")
        file_menu.addAction(self._make_action("Beenden", self.close, "Ctrl+Q"))

        # Verzeichnisse
        dir_menu = mb.addMenu("&Verzeichnisse")
        dir_menu.addAction(self._make_action("Verzeichnis hinzufuegen...", self._add_directory, "Ctrl+O"))
        dir_menu.addAction(self._make_action("Alle scannen", self._scan_all))

        # Ansicht
        view_menu = mb.addMenu("&Ansicht")
        view_menu.addAction(self._make_action("Web-Viewer starten", self._start_web_viewer))
        view_menu.addAction(self._make_action("Aktualisieren", self._refresh, "F5"))

        # Hilfe
        help_menu = mb.addMenu("&Hilfe")
        help_menu.addAction(self._make_action("Ueber KnowledgeDigest", self._show_about))

    def _setup_toolbar(self):
        """Erstellt die Toolbar."""
        tb = QToolBar("Hauptwerkzeuge")
        tb.setIconSize(QSize(16, 16))
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self._make_action("+ Verzeichnis", self._add_directory))
        tb.addAction(self._make_action("Scannen", self._scan_all))
        tb.addSeparator()

        self._search_bar = SearchBar(self._kd)
        tb.addWidget(self._search_bar)

        tb.addSeparator()
        tb.addAction(self._make_action("Web-Viewer", self._start_web_viewer))
        tb.addAction(self._make_action("Einstellungen", self._show_settings))

    def _setup_panels(self):
        """Erstellt das 3-Panel-Layout."""
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._dir_panel = DirectoryPanel(self._kd)
        self._doc_list = DocumentListPanel(self._kd)
        self._preview = PreviewPanel()

        self._splitter.addWidget(self._dir_panel)
        self._splitter.addWidget(self._doc_list)
        self._splitter.addWidget(self._preview)

        sizes = self._config.get("splitter_sizes", [220, 350, 430])
        self._splitter.setSizes(sizes)

        self.setCentralWidget(self._splitter)

    def _setup_statusbar(self):
        """Erstellt die Statusleiste."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel()
        self._statusbar.addPermanentWidget(self._status_label)

    def _connect_events(self):
        """Verbindet EventBus-Events."""
        self._bus.subscribe(EventType.DIRECTORY_SELECTED, self._on_directory_selected)
        self._bus.subscribe(EventType.DOCUMENT_SELECTED, self._on_document_selected)
        self._bus.subscribe(EventType.SEARCH_COMPLETED, self._on_search_completed)
        self._bus.subscribe(EventType.STATUS_MESSAGE, self._on_status_message)
        self._bus.subscribe(EventType.DB_UPDATED, lambda _: self._update_status())
        self._bus.subscribe(EventType.DIRECTORY_SCAN_FINISHED, lambda _: self._refresh(None))

    def _on_directory_selected(self, path):
        """Verzeichnis wurde ausgewaehlt -> Dokumentenliste filtern."""
        self._doc_list.filter_by_directory(path)

    def _on_document_selected(self, doc_data):
        """Dokument wurde ausgewaehlt -> Vorschau anzeigen."""
        if doc_data:
            self._preview.show_document(doc_data)

    def _on_search_completed(self, results):
        """Suchergebnisse anzeigen."""
        self._doc_list.show_search_results(results)

    def _on_status_message(self, msg):
        """Statusbar-Nachricht."""
        self._statusbar.showMessage(str(msg), 5000)

    def _update_status(self):
        """Aktualisiert die Statusleiste."""
        try:
            status = self._kd.get_status()
            docs = status.get("documents", {})
            total = docs.get("total_documents", 0)
            chunks = docs.get("total_chunks", 0)
            db_kb = status.get("db_size_kb", 0)
            db_mb = round(db_kb / 1024, 1) if db_kb else 0
            self._status_label.setText(
                f"  {total} Dokumente  |  {chunks} Chunks  |  DB: {db_mb} MB  "
            )
        except Exception:
            self._status_label.setText("  DB nicht verfuegbar  ")

    # --- Actions ---

    def _add_directory(self):
        """Verzeichnis hinzufuegen via Dialog."""
        path = QFileDialog.getExistingDirectory(
            self, "Verzeichnis zum Indexieren auswaehlen"
        )
        if path:
            result = self._kd.add_directory(path)
            if result.get("ok"):
                self._bus.emit(EventType.DIRECTORY_ADDED, path)
                self._bus.emit(EventType.STATUS_MESSAGE, f"Verzeichnis hinzugefuegt: {path}")
                self._dir_panel.refresh()

    def _scan_all(self):
        """Scannt alle indexierten Verzeichnisse."""
        dirs = self._kd.get_directories()
        if not dirs:
            QMessageBox.information(self, "Scannen", "Keine Verzeichnisse konfiguriert.")
            return
        self._bus.emit(EventType.STATUS_MESSAGE, f"Scanne {len(dirs)} Verzeichnisse...")
        self._bus.emit(EventType.DIRECTORY_SCAN_STARTED, None)

        # In separatem Thread scannen
        def _scan():
            for d in dirs:
                self._kd.scan_directory(d["path"], recursive=True, archive=False)
            self._bus.emit(EventType.DIRECTORY_SCAN_FINISHED, None)
            self._bus.emit(EventType.DB_UPDATED, None)
            self._bus.emit(EventType.STATUS_MESSAGE, "Scan abgeschlossen.")

        threading.Thread(target=_scan, daemon=True).start()

    def _start_web_viewer(self):
        """Startet den Web-Viewer in einem Thread."""
        if self._web_server:
            self._bus.emit(EventType.STATUS_MESSAGE, "Web-Viewer laeuft bereits.")
            return
        try:
            from ..web_viewer import start_server_thread
            port = self._config.get("web_port", 8787)
            db_path = self._kd.db_path
            self._web_server = start_server_thread(db_path, port)
            self._bus.emit(EventType.WEB_SERVER_STARTED, port)
            self._bus.emit(EventType.STATUS_MESSAGE, f"Web-Viewer gestartet: http://127.0.0.1:{port}")

            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception as e:
            QMessageBox.warning(self, "Web-Viewer", f"Fehler: {e}")

    def _show_settings(self):
        """Oeffnet den Settings-Dialog."""
        from .dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._config, parent=self)
        if dlg.exec():
            self._bus.emit(EventType.STATUS_MESSAGE, "Einstellungen gespeichert.")
            self._update_status()

    def _refresh(self, _=None):
        """Aktualisiert alle Panels."""
        self._dir_panel.refresh()
        self._doc_list.refresh()
        self._update_status()

    def _show_about(self):
        """Zeigt Info-Dialog."""
        QMessageBox.about(
            self, "KnowledgeDigest",
            "KnowledgeDigest -- Portable Wissensdatenbank\n\n"
            "Indexiert Dokumente (PDF, DOCX, TXT, MD, HTML),\n"
            "chunked den Content und macht ihn durchsuchbar.\n\n"
            "Autor: Lukas Geiger"
        )

    def _make_action(self, text, slot, shortcut=None):
        """Erstellt eine QAction."""
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(shortcut)
        return action

    # --- State ---

    def _restore_state(self):
        """Stellt Fensterposition wieder her."""
        geo = self._config.get("window_geometry")
        if geo:
            try:
                self.restoreGeometry(bytes.fromhex(geo))
            except Exception:
                self.resize(1100, 700)
        else:
            self.resize(1100, 700)

    def _save_state(self):
        """Speichert Fensterposition und Splitter."""
        self._config.set("window_geometry", self.saveGeometry().toHex().data().decode())
        self._config.set("splitter_sizes", self._splitter.sizes())
        self._config.save()

    def closeEvent(self, event):
        """Speichert State beim Schliessen."""
        self._save_state()
        self._kd.close()
        super().closeEvent(event)
