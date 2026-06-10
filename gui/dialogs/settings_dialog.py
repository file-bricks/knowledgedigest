# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Settings Dialog.
Tab-basierter Einstellungsdialog.
Adaptiert von DokuZentrum (gui/dialogs/settings_dialog.py).
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QFileDialog,
    QDialogButtonBox, QHBoxLayout, QListWidget, QLabel
)


class SettingsDialog(QDialog):
    """Einstellungsdialog mit Tabs."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Einstellungen")
        self.setMinimumSize(500, 400)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Tab 1: Allgemein
        self._tab_general = QWidget()
        form = QFormLayout(self._tab_general)

        self._edit_db = QLineEdit()
        btn_db = QPushButton("...")
        btn_db.setFixedWidth(30)
        btn_db.clicked.connect(self._browse_db)
        row_db = QHBoxLayout()
        row_db.addWidget(self._edit_db)
        row_db.addWidget(btn_db)
        form.addRow("DB-Pfad:", row_db)

        self._edit_inbox = QLineEdit()
        form.addRow("Inbox-Pfad:", self._edit_inbox)

        self._edit_archive = QLineEdit()
        form.addRow("Archive-Pfad:", self._edit_archive)

        self._spin_port = QSpinBox()
        self._spin_port.setRange(1024, 65535)
        form.addRow("Web-Viewer Port:", self._spin_port)

        self._tabs.addTab(self._tab_general, "Allgemein")

        # Tab 2: Verzeichnisse
        self._tab_dirs = QWidget()
        dl = QVBoxLayout(self._tab_dirs)
        dl.addWidget(QLabel("Indexierte Verzeichnisse:"))

        self._dir_list = QListWidget()
        dl.addWidget(self._dir_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Hinzufuegen...")
        btn_add.clicked.connect(self._add_dir)
        btn_remove = QPushButton("Entfernen")
        btn_remove.clicked.connect(self._remove_dir)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        dl.addLayout(btn_row)

        self._tabs.addTab(self._tab_dirs, "Verzeichnisse")

        # Tab 3: Ingestion
        self._tab_ingest = QWidget()
        fi = QFormLayout(self._tab_ingest)

        self._spin_chunk = QSpinBox()
        self._spin_chunk.setRange(50, 2000)
        fi.addRow("Chunk-Groesse (Woerter):", self._spin_chunk)

        self._spin_overlap = QSpinBox()
        self._spin_overlap.setRange(0, 200)
        fi.addRow("Chunk-Overlap:", self._spin_overlap)

        self._check_archive = QCheckBox("Originale archivieren")
        fi.addRow("", self._check_archive)

        self._check_recursive = QCheckBox("Unterordner einbeziehen")
        fi.addRow("", self._check_recursive)

        self._spin_min_words = QSpinBox()
        self._spin_min_words.setRange(0, 1000)
        fi.addRow("Mindest-Woerter:", self._spin_min_words)

        self._tabs.addTab(self._tab_ingest, "Ingestion")

        # Tab 4: BACH (optional)
        self._tab_bach = QWidget()
        fb = QFormLayout(self._tab_bach)

        self._check_bach = QCheckBox("BACH-Integration aktivieren")
        fb.addRow("", self._check_bach)

        self._edit_bach_db = QLineEdit()
        btn_bach = QPushButton("...")
        btn_bach.setFixedWidth(30)
        btn_bach.clicked.connect(self._browse_bach_db)
        row_bach = QHBoxLayout()
        row_bach.addWidget(self._edit_bach_db)
        row_bach.addWidget(btn_bach)
        fb.addRow("bach.db Pfad:", row_bach)

        self._tabs.addTab(self._tab_bach, "BACH")

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_values(self):
        self._edit_db.setText(self._config.get("db_path", ""))
        self._edit_inbox.setText(self._config.get("inbox_dir", ""))
        self._edit_archive.setText(self._config.get("archive_dir", ""))
        self._spin_port.setValue(self._config.get("web_port", 8787))
        self._spin_chunk.setValue(self._config.get("chunk_size", 350))
        self._spin_overlap.setValue(self._config.get("chunk_overlap", 0))
        self._check_archive.setChecked(self._config.get("auto_archive", True))
        self._check_recursive.setChecked(self._config.get("recursive_scan", True))
        self._spin_min_words.setValue(self._config.get("min_words", 10))
        self._check_bach.setChecked(self._config.get("bach_enabled", False))
        self._edit_bach_db.setText(self._config.get("bach_db_path", ""))

        for d in self._config.get_indexed_directories():
            self._dir_list.addItem(d)

    def _save_and_accept(self):
        self._config.set("db_path", self._edit_db.text())
        self._config.set("inbox_dir", self._edit_inbox.text())
        self._config.set("archive_dir", self._edit_archive.text())
        self._config.set("web_port", self._spin_port.value())
        self._config.set("chunk_size", self._spin_chunk.value())
        self._config.set("chunk_overlap", self._spin_overlap.value())
        self._config.set("auto_archive", self._check_archive.isChecked())
        self._config.set("recursive_scan", self._check_recursive.isChecked())
        self._config.set("min_words", self._spin_min_words.value())
        self._config.set("bach_enabled", self._check_bach.isChecked())
        self._config.set("bach_db_path", self._edit_bach_db.text())

        dirs = [self._dir_list.item(i).text() for i in range(self._dir_list.count())]
        self._config.set("indexed_directories", dirs)

        self._config.save()
        self.accept()

    def _browse_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "DB-Datei waehlen", "", "SQLite (*.db)")
        if path:
            self._edit_db.setText(path)

    def _browse_bach_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "bach.db waehlen", "", "SQLite (*.db)")
        if path:
            self._edit_bach_db.setText(path)

    def _add_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Verzeichnis auswaehlen")
        if path:
            self._dir_list.addItem(str(Path(path).resolve()))

    def _remove_dir(self):
        row = self._dir_list.currentRow()
        if row >= 0:
            self._dir_list.takeItem(row)
