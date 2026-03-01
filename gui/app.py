# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- GUI Application Entry Point.
Startet die PyQt6-Anwendung mit Dark Theme.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt


def _apply_dark_palette(app: QApplication):
    """Setzt ein dunkles Farbschema (passend zum Web-Viewer)."""
    palette = QPalette()

    # Hintergrund
    palette.setColor(QPalette.ColorRole.Window, QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#161b22"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c2128"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))

    # Buttons
    palette.setColor(QPalette.ColorRole.Button, QColor("#21262d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e6edf3"))

    # Highlights
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#58a6ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

    # Disabled
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#484f58"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#484f58"))

    # Tooltip
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1c2128"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e6edf3"))

    # Links
    palette.setColor(QPalette.ColorRole.Link, QColor("#58a6ff"))

    app.setPalette(palette)


STYLESHEET = """
QMainWindow, QDialog {
    background-color: #0d1117;
}
QToolBar {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
    spacing: 4px;
    padding: 2px;
}
QToolBar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e6edf3;
}
QToolBar QToolButton:hover {
    background: #21262d;
    border-color: #30363d;
}
QStatusBar {
    background-color: #161b22;
    border-top: 1px solid #30363d;
    color: #8b949e;
}
QTreeWidget, QTableWidget, QTextEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    color: #e6edf3;
    selection-background-color: #1f3a5f;
}
QTreeWidget::item:hover, QTableWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.06);
}
QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    border: 1px solid #30363d;
    padding: 4px 8px;
    font-weight: bold;
}
QSplitter::handle {
    background-color: #30363d;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QPushButton {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 12px;
    color: #e6edf3;
}
QPushButton:hover {
    background-color: #30363d;
}
QPushButton:pressed {
    background-color: #1f3a5f;
}
QLineEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e6edf3;
}
QLineEdit:focus {
    border-color: #58a6ff;
}
QMenuBar {
    background-color: #161b22;
    color: #e6edf3;
    border-bottom: 1px solid #30363d;
}
QMenuBar::item:selected {
    background-color: #21262d;
}
QMenu {
    background-color: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
}
QMenu::item:selected {
    background-color: #1f3a5f;
}
QTabWidget::pane {
    border: 1px solid #30363d;
    background: #0d1117;
}
QTabBar::tab {
    background: #161b22;
    border: 1px solid #30363d;
    padding: 6px 12px;
    color: #8b949e;
}
QTabBar::tab:selected {
    background: #0d1117;
    color: #e6edf3;
    border-bottom-color: #0d1117;
}
QProgressBar {
    border: 1px solid #30363d;
    border-radius: 4px;
    text-align: center;
    color: #e6edf3;
    background: #0d1117;
}
QProgressBar::chunk {
    background-color: #3fb950;
    border-radius: 3px;
}
QScrollBar:vertical {
    background: #0d1117;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def launch_gui():
    """Startet die KnowledgeDigest GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("KnowledgeDigest")
    app.setOrganizationName("KnowledgeDigest")

    _apply_dark_palette(app)
    app.setStyleSheet(STYLESHEET)

    from .main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()
