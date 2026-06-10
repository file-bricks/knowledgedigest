# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Config-System.

JSON-basierte Konfiguration fuer portable Nutzung.
Keine hardcodierten Pfade, alles konfigurierbar.

Usage:
    from .config import get_config, Config

    cfg = get_config()
    db_path = cfg.get("db_path")
    cfg.set("web_port", 9000)
    cfg.save()
"""

__all__ = ["Config", "get_config"]

import json
import os
from pathlib import Path
from typing import Any, Optional

CONFIG_FILENAME = "knowledgedigest.json"

_MODULE_DIR = Path(__file__).parent
_DATA_DIR = _MODULE_DIR / "data"

DEFAULT_CONFIG = {
    # Pfade
    "db_path": "",
    "indexed_directories": [],
    "inbox_dir": "",
    "archive_dir": "",

    # BACH (optional)
    "bach_db_path": "",
    "bach_enabled": False,

    # Ingestion
    "chunk_size": 350,
    "chunk_overlap": 0,
    "auto_archive": True,
    "recursive_scan": True,
    "min_words": 10,

    # Summarization
    "summarize_model": "claude-haiku-4-5",
    "summarize_delay": 0.5,

    # Web-Viewer
    "web_port": 8787,
    "web_auto_open": True,

    # GUI
    "window_geometry": None,
    "window_state": None,
    "splitter_sizes": [220, 350, 430],
    "theme": "dark",
    "font_size": 10,
    "recent_searches": [],
}


class Config:
    """JSON-basierte Konfiguration."""

    def __init__(self, config_path: Optional[Path] = None):
        self._data = dict(DEFAULT_CONFIG)
        self._path = config_path
        if config_path and config_path.exists():
            self._load(config_path)
        elif not config_path:
            self._path = self._find_config()
            if self._path and self._path.exists():
                self._load(self._path)

    def _find_config(self) -> Optional[Path]:
        """Sucht Config-Datei in Standard-Orten."""
        candidates = [
            Path.cwd() / CONFIG_FILENAME,
            _DATA_DIR / CONFIG_FILENAME,
            Path(os.environ.get("APPDATA", "")) / "KnowledgeDigest" / CONFIG_FILENAME,
        ]
        for p in candidates:
            if p.exists():
                return p
        # Default: neben data/
        return _DATA_DIR / CONFIG_FILENAME

    def _load(self, path: Path):
        """Laedt Config aus JSON-Datei."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self._data.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass

    def get(self, key: str, default: Any = None) -> Any:
        """Gibt Config-Wert zurueck."""
        val = self._data.get(key, default)
        if val is None and default is not None:
            return default
        return val

    def set(self, key: str, value: Any):
        """Setzt Config-Wert."""
        self._data[key] = value

    def save(self):
        """Speichert Config als JSON."""
        path = self._path or (_DATA_DIR / CONFIG_FILENAME)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get_db_path(self) -> Path:
        """Gibt den DB-Pfad zurueck (mit Fallback auf Default)."""
        p = self.get("db_path", "")
        if p:
            return Path(p)
        return _DATA_DIR / "knowledge.db"

    def get_inbox_dir(self) -> Path:
        """Gibt den Inbox-Pfad zurueck."""
        p = self.get("inbox_dir", "")
        if p:
            return Path(p)
        return _DATA_DIR / "inbox"

    def get_archive_dir(self) -> Path:
        """Gibt den Archive-Pfad zurueck."""
        p = self.get("archive_dir", "")
        if p:
            return Path(p)
        return _DATA_DIR / "archive"

    def get_indexed_directories(self) -> list:
        """Gibt Liste der indexierten Verzeichnisse zurueck."""
        return self.get("indexed_directories", [])

    def add_directory(self, path: str):
        """Fuegt Verzeichnis zur Index-Liste hinzu."""
        dirs = self.get_indexed_directories()
        norm = str(Path(path).resolve())
        if norm not in dirs:
            dirs.append(norm)
            self.set("indexed_directories", dirs)
            self.save()

    def remove_directory(self, path: str):
        """Entfernt Verzeichnis aus Index-Liste."""
        dirs = self.get_indexed_directories()
        norm = str(Path(path).resolve())
        if norm in dirs:
            dirs.remove(norm)
            self.set("indexed_directories", dirs)
            self.save()

    @property
    def data(self) -> dict:
        """Gibt alle Config-Daten zurueck."""
        return dict(self._data)


# Singleton
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[Path] = None) -> Config:
    """Gibt die globale Config-Instanz zurueck."""
    global _config_instance
    if _config_instance is None or config_path:
        _config_instance = Config(config_path)
    return _config_instance
