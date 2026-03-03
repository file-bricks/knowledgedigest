# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- GUI Launcher.

Erstellt fehlende Ordner/Dateien und startet die GUI.
Wird zu einer EXE kompiliert fuer einfachen Start per Doppelklick.
"""

import os
import sys
import json
from pathlib import Path


def get_base_dir():
    """Ermittelt das Basisverzeichnis (neben der EXE oder neben launcher.py)."""
    if getattr(sys, "frozen", False):
        # PyInstaller EXE
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


def ensure_structure(base: Path):
    """Erstellt fehlende Ordner und Dateien."""
    # Ordner
    dirs = [
        base / "data",
        base / "data" / "inbox",
        base / "data" / "archive",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Config-Datei
    config_path = base / "data" / "knowledgedigest.json"
    if not config_path.exists():
        default_config = {
            "db_path": "",
            "indexed_directories": [],
            "inbox_dir": "",
            "archive_dir": "",
            "bach_db_path": "",
            "bach_enabled": False,
            "chunk_size": 350,
            "chunk_overlap": 0,
            "auto_archive": True,
            "recursive_scan": True,
            "min_words": 10,
            "summarize_model": "claude-haiku-4-5",
            "summarize_delay": 0.5,
            "web_port": 8787,
            "web_auto_open": True,
            "window_geometry": None,
            "window_state": None,
            "splitter_sizes": [220, 350, 430],
            "theme": "dark",
            "font_size": 10,
            "recent_searches": [],
        }
        config_path.write_text(json.dumps(default_config, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Config erstellt: {config_path}")

    # .gitkeep
    gitkeep = base / "data" / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()


def main():
    base = get_base_dir()
    print(f"KnowledgeDigest Launcher")
    print(f"Basis: {base}")

    # Struktur sicherstellen
    ensure_structure(base)

    # Sicherstellen dass das Paket importierbar ist
    if str(base.parent) not in sys.path:
        sys.path.insert(0, str(base.parent))
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    # GUI starten
    os.environ["PYTHONIOENCODING"] = "utf-8"

    from KnowledgeDigest.gui.app import launch_gui
    sys.exit(launch_gui())


if __name__ == "__main__":
    main()
