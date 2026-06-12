# -*- coding: utf-8 -*-
"""
Regressionstests fuer GeminiFlashSummarizer (Konstruktor + CLI-Aufrufstelle).

Hintergrund (Audit 2026-06-12): digest.py rief den Konstruktor mit
vertauschten Argumenten auf -- GeminiFlashSummarizer(api_key, kd.db_path)
statt (kd.db_path, api_key). Diese Tests fixieren die korrekte Reihenfolge.

Keine echten API-Calls: Konstruktor-Tests + gemockte CLI-Aufrufstelle.
"""

import importlib
import sys
from pathlib import Path

# Modulpfad einfuegen (tests/ ist ein Unterordner von KnowledgeDigest/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from gemini_flash_summarizer import GeminiFlashSummarizer, _DEFAULT_MODEL


def _import_package_modules():
    """Import digest + gemini_flash_summarizer as package modules.

    digest.py uses package-relative imports (``from .schema import ...``),
    so it must be imported as KnowledgeDigest.digest. Returns the digest
    module and the matching gemini_flash_summarizer module instance
    (the one digest's ``from .gemini_flash_summarizer import ...`` uses).
    """
    pkg_parent = str(Path(__file__).parent.parent.parent)
    if pkg_parent not in sys.path:
        sys.path.insert(0, pkg_parent)
    digest_mod = importlib.import_module("KnowledgeDigest.digest")
    gfs_mod = importlib.import_module("KnowledgeDigest.gemini_flash_summarizer")
    return digest_mod, gfs_mod


class TestConstructorArgumentOrder:
    def test_first_positional_is_knowledge_db(self, tmp_path):
        db = tmp_path / "knowledge.db"
        s = GeminiFlashSummarizer(db, api_key="test-key")
        assert s.knowledge_db == db
        assert s._api_key == "test-key"

    def test_api_key_falls_back_to_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        s = GeminiFlashSummarizer(tmp_path / "knowledge.db")
        assert s._api_key == "env-key"

    def test_no_connection_opened_in_constructor(self, tmp_path):
        # Constructor must be lazy -- no DB file created on instantiation
        db = tmp_path / "knowledge.db"
        GeminiFlashSummarizer(db, api_key="test-key")
        assert not db.exists()


class TestModelConfiguration:
    def test_default_model(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        s = GeminiFlashSummarizer(tmp_path / "knowledge.db", api_key="k")
        assert s.model == _DEFAULT_MODEL
        assert s.model == "gemini-2.0-flash"

    def test_model_param_overrides_default(self, tmp_path):
        s = GeminiFlashSummarizer(tmp_path / "knowledge.db", api_key="k",
                                  model="gemini-2.5-flash")
        assert s.model == "gemini-2.5-flash"

    def test_model_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-9.9-flash")
        s = GeminiFlashSummarizer(tmp_path / "knowledge.db", api_key="k")
        assert s.model == "gemini-9.9-flash"

    def test_param_beats_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "env-model")
        s = GeminiFlashSummarizer(tmp_path / "knowledge.db", api_key="k",
                                  model="param-model")
        assert s.model == "param-model"


class TestDigestFlashCallSite:
    """Regression: digest.py 'summarize --flash' muss (db_path, api_key=...)
    uebergeben -- nicht vertauscht."""

    def test_cli_passes_db_path_and_api_key_correctly(self, tmp_path, monkeypatch):
        digest, gfs_mod = _import_package_modules()

        calls = {}

        class FakeSummarizer:
            def __init__(self, knowledge_db, api_key=None, model=None):
                calls["knowledge_db"] = knowledge_db
                calls["api_key"] = api_key

            def summarize_queue(self, *, limit=10, delay=0.5):
                calls["limit"] = limit
                return {}

        class DummyKD:
            db_path = tmp_path / "knowledge.db"

            def close(self):
                pass

        monkeypatch.setattr(gfs_mod, "GeminiFlashSummarizer", FakeSummarizer)
        monkeypatch.setattr(digest, "KnowledgeDigest", DummyKD)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(sys, "argv",
                            ["digest.py", "summarize", "--flash", "--limit", "3"])

        rc = digest.main()

        assert rc == 0
        # The DB path must arrive as knowledge_db -- NOT as api_key
        assert calls["knowledge_db"] == DummyKD.db_path
        assert calls["api_key"] == "fake-key"
        assert calls["limit"] == 3

    def test_cli_missing_api_key_returns_error_code(self, tmp_path, monkeypatch):
        digest, _ = _import_package_modules()

        class DummyKD:
            db_path = tmp_path / "knowledge.db"

            def close(self):
                pass

        monkeypatch.setattr(digest, "KnowledgeDigest", DummyKD)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setattr(sys, "argv", ["digest.py", "summarize", "--flash"])

        rc = digest.main()
        assert rc == 1
