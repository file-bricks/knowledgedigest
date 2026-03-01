# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Directory Panel.
Zeigt indexierte Verzeichnisse als Baumansicht.
Adaptiert von DokuZentrum (gui/panels/library_panel.py).
"""

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QMenu, QMessageBox, QLabel, QHBoxLayout, QPushButton,
    QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from ..event_bus import EventType, get_event_bus


class DirectoryPanel(QWidget):
    """Panel zur Anzeige indexierter Verzeichnisse."""

    def __init__(self, kd, parent=None):
        super().__init__(parent)
        self._kd = kd
        self._bus = get_event_bus()
        self._setup_ui()
        self._connect_signals()
        self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Verzeichnisse</b>"))

        self._btn_add = QPushButton("+")
        self._btn_add.setFixedSize(24, 24)
        self._btn_add.setToolTip("Verzeichnis hinzufuegen")
        self._btn_add.clicked.connect(self._add_directory)
        header.addWidget(self._btn_add)

        layout.addLayout(header)

        # Baum
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.setIndentation(15)
        self._tree.setAnimated(True)
        layout.addWidget(self._tree)

    def _connect_signals(self):
        self._tree.currentItemChanged.connect(self._on_item_changed)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)

    def _populate(self):
        """Fuellt den Baum mit indexierten Verzeichnissen."""
        self._tree.clear()

        # "Alle Dokumente" als erstes Item
        all_item = QTreeWidgetItem()
        all_item.setText(0, "Alle Dokumente")
        all_item.setData(0, Qt.ItemDataRole.UserRole, "__all__")
        self._tree.addTopLevelItem(all_item)

        dirs = self._kd.get_directories()
        for d in dirs:
            item = QTreeWidgetItem()
            name = Path(d["path"]).name
            count = d.get("doc_count", 0)
            item.setText(0, f"{name} ({count})")
            item.setData(0, Qt.ItemDataRole.UserRole, d["path"])
            item.setToolTip(0, d["path"])
            self._tree.addTopLevelItem(item)

        # Erstes Item auswaehlen
        if self._tree.topLevelItemCount() > 0:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))

    def refresh(self):
        self._populate()

    def _add_directory(self):
        """Oeffnet Dialog zum Hinzufuegen."""
        path = QFileDialog.getExistingDirectory(
            self, "Verzeichnis zum Indexieren auswaehlen"
        )
        if path:
            result = self._kd.add_directory(path)
            if result.get("ok"):
                self._bus.emit(EventType.DIRECTORY_ADDED, path)
                self._bus.emit(EventType.STATUS_MESSAGE, f"Hinzugefuegt: {path}")
                self.refresh()

    def _on_item_changed(self, current, previous):
        if current:
            path = current.data(0, Qt.ItemDataRole.UserRole)
            self._bus.emit(EventType.DIRECTORY_SELECTED, path)

    def _show_context_menu(self, position):
        item = self._tree.itemAt(position)
        if not item:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or path == "__all__":
            return

        menu = QMenu(self)

        action_scan = QAction("Neu scannen", self)
        action_scan.triggered.connect(lambda: self._scan_directory(path))
        menu.addAction(action_scan)

        action_explorer = QAction("Im Explorer oeffnen", self)
        action_explorer.triggered.connect(lambda: self._open_in_explorer(path))
        menu.addAction(action_explorer)

        menu.addSeparator()

        action_remove = QAction("Entfernen", self)
        action_remove.triggered.connect(lambda: self._remove_directory(path))
        menu.addAction(action_remove)

        menu.exec(self._tree.mapToGlobal(position))

    def _scan_directory(self, path):
        self._bus.emit(EventType.STATUS_MESSAGE, f"Scanne: {path}...")
        self._bus.emit(EventType.DIRECTORY_SCAN_STARTED, path)

        import threading
        def _scan():
            self._kd.scan_directory(path, recursive=True, archive=False)
            self._bus.emit(EventType.DIRECTORY_SCAN_FINISHED, path)
            self._bus.emit(EventType.DB_UPDATED, None)
            self._bus.emit(EventType.STATUS_MESSAGE, f"Scan abgeschlossen: {path}")

        threading.Thread(target=_scan, daemon=True).start()

    def _open_in_explorer(self, path):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def _remove_directory(self, path):
        result = QMessageBox.question(
            self, "Verzeichnis entfernen",
            f"Verzeichnis aus der Index-Liste entfernen?\n\n{path}\n\n"
            "(Die Dateien werden nicht geloescht, nur aus der Liste entfernt.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result == QMessageBox.StandardButton.Yes:
            self._kd.remove_directory(path)
            self._bus.emit(EventType.DIRECTORY_REMOVED, path)
            self._bus.emit(EventType.STATUS_MESSAGE, f"Entfernt: {path}")
            self.refresh()
