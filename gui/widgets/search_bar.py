# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Search Bar Widget.
FTS5-Suchleiste fuer die Toolbar.
"""

from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import Qt

from ..event_bus import EventType, get_event_bus


class SearchBar(QLineEdit):
    """Suchleiste mit FTS5-Integration."""

    def __init__(self, kd, parent=None):
        super().__init__(parent)
        self._kd = kd
        self._bus = get_event_bus()

        self.setPlaceholderText("Suche (FTS5)...")
        self.setMinimumWidth(200)
        self.setMaximumWidth(400)
        self.returnPressed.connect(self._do_search)

    def _do_search(self):
        query = self.text().strip()
        if not query:
            return

        self._bus.emit(EventType.SEARCH_STARTED, query)
        self._bus.emit(EventType.STATUS_MESSAGE, f"Suche: {query}...")

        try:
            results = self._kd.search_all(query, limit=50)
            self._bus.emit(EventType.SEARCH_COMPLETED, results)
        except Exception as e:
            self._bus.emit(EventType.ERROR_MESSAGE, f"Suchfehler: {e}")
