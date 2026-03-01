# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Event Bus
Zentrale Event-Verteilung zwischen GUI-Modulen.
Adaptiert von LitZentrum (src/core/event_bus.py).
"""

from PySide6.QtCore import QObject, Signal
from enum import Enum
from typing import Any, Callable, Dict, List


class EventType(Enum):
    """Alle Event-Typen in KnowledgeDigest GUI"""

    # Verzeichnis-Events
    DIRECTORY_ADDED = "directory_added"
    DIRECTORY_REMOVED = "directory_removed"
    DIRECTORY_SELECTED = "directory_selected"
    DIRECTORY_SCAN_STARTED = "directory_scan_started"
    DIRECTORY_SCAN_FINISHED = "directory_scan_finished"

    # Dokument-Events
    DOCUMENT_SELECTED = "document_selected"
    DOCUMENT_INGESTED = "document_ingested"

    # Suche
    SEARCH_STARTED = "search_started"
    SEARCH_COMPLETED = "search_completed"

    # Status
    STATUS_MESSAGE = "status_message"
    ERROR_MESSAGE = "error_message"
    DB_UPDATED = "db_updated"
    REFRESH_VIEW = "refresh_view"

    # Web-Viewer
    WEB_SERVER_STARTED = "web_server_started"
    WEB_SERVER_STOPPED = "web_server_stopped"


class EventBus(QObject):
    """Zentrale Event-Verteilung (Singleton)"""

    event_fired = Signal(str, object)

    _instance = None

    def __init__(self):
        super().__init__()
        self._handlers: Dict[EventType, List[Callable]] = {}

    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, event_type: EventType, handler: Callable[[Any], None]):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable):
        if event_type in self._handlers:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

    def emit(self, event_type: EventType, data: Any = None):
        self.event_fired.emit(event_type.value, data)
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"[EventBus] Handler-Fehler bei {event_type.value}: {e}")

    def clear(self):
        self._handlers.clear()


def get_event_bus() -> EventBus:
    return EventBus.instance()
