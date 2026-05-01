# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec fuer KnowledgeDigest GUI Launcher.
Baut eine einzelne EXE die fehlende Ordner anlegt und die GUI startet.
"""

import os
import sys
from pathlib import Path

block_cipher = None

BASE = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(BASE, 'launcher.py')],
    pathex=[os.path.dirname(BASE)],  # Parent dir so KnowledgeDigest package is findable
    binaries=[],
    datas=[
        (os.path.join(BASE, 'KnowledgeDigest.ico'), '.'),
    ],
    hiddenimports=[
        'KnowledgeDigest',
        'KnowledgeDigest.config',
        'KnowledgeDigest.digest',
        'KnowledgeDigest.schema',
        'KnowledgeDigest.extractor',
        'KnowledgeDigest.chunker',
        'KnowledgeDigest.ingestor',
        'KnowledgeDigest.summarizer',
        'KnowledgeDigest.utils',
        'KnowledgeDigest.web_viewer',
        'KnowledgeDigest.gui',
        'KnowledgeDigest.gui.app',
        'KnowledgeDigest.gui.event_bus',
        'KnowledgeDigest.gui.main_window',
        'KnowledgeDigest.gui.panels',
        'KnowledgeDigest.gui.panels.directory_panel',
        'KnowledgeDigest.gui.panels.document_list',
        'KnowledgeDigest.gui.panels.preview_panel',
        'KnowledgeDigest.gui.widgets',
        'KnowledgeDigest.gui.widgets.search_bar',
        'KnowledgeDigest.gui.dialogs',
        'KnowledgeDigest.gui.dialogs.settings_dialog',
        'KnowledgeDigest.gui.dialogs.ingest_dialog',
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6',  # Nicht mitliefern
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KnowledgeDigest',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Kein Konsolenfenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(BASE, 'KnowledgeDigest.ico'),
)
