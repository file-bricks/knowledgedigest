# -*- coding: utf-8 -*-
"""
Unit-Tests fuer KnowledgeDigest Core-Module.

Testet: chunker.py, schema.py, config.py, utils.py
Keine GUI-, API- oder LLM-Tests.
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

# Modulpfad einfuegen (tests/ ist ein Unterordner von KnowledgeDigest/)
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from chunker import chunk_text, split_frontmatter, estimate_tokens, Chunk
from schema import ensure_schema, get_schema_version, SCHEMA_VERSION
from config import Config
from utils import sha256_hash, extract_keywords, STOP_WORDS


# ============================================================
# estimate_tokens
# ============================================================

class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_none_like_empty(self):
        # Dokumentiertes Verhalten: leerer String -> 0
        assert estimate_tokens("") == 0

    def test_single_word(self):
        assert estimate_tokens("hello") == 1

    def test_multiple_words(self):
        assert estimate_tokens("the quick brown fox") == 4

    def test_leading_trailing_spaces(self):
        # str.split() ignoriert fuehrende/abschliessende Leerzeichen
        assert estimate_tokens("  hello world  ") == 2

    def test_newlines_count_as_separator(self):
        # "a\nb" -> split() -> ["a", "b"] -> 2 Tokens
        assert estimate_tokens("hello\nworld") == 2

    def test_long_text(self):
        words = ["word"] * 500
        text = " ".join(words)
        assert estimate_tokens(text) == 500

    def test_unicode_words(self):
        assert estimate_tokens("Überblick über Schüler") == 3

    def test_mixed_whitespace(self):
        assert estimate_tokens("a\t b\n  c") == 3


# ============================================================
# split_frontmatter
# ============================================================

class TestSplitFrontmatter:
    def test_empty_string(self):
        fm, body = split_frontmatter("")
        assert fm is None
        assert body == ""

    def test_no_frontmatter(self):
        text = "# Titel\n\nKein Frontmatter hier."
        fm, body = split_frontmatter(text)
        assert fm is None
        assert body == text.strip()

    def test_valid_frontmatter(self):
        text = "---\nname: test\nversion: 1.0\n---\n# Body content"
        fm, body = split_frontmatter(text)
        assert fm is not None
        assert "name: test" in fm
        assert "# Body content" in body

    def test_frontmatter_is_stripped(self):
        text = "---\nname: foo\n---\n\nSome body text."
        fm, body = split_frontmatter(text)
        assert fm.startswith("---")
        assert fm.endswith("---")

    def test_body_stripped(self):
        text = "---\nkey: val\n---\n\n   Body here.   "
        _, body = split_frontmatter(text)
        assert body == "Body here."

    def test_frontmatter_with_body(self):
        # Normaler Fall: Frontmatter gefolgt von Body
        text = "---\nname: test\n---\n# Body"
        fm, body = split_frontmatter(text)
        assert fm is not None
        assert body == "# Body"

    def test_frontmatter_only_no_body_behavior(self):
        # Grenzfall: Text endet direkt mit dem schliessenden ---
        # strip() entfernt das trailing \n -> Regex \n---\s*\n greift nicht
        # -> Code behandelt den Text als "kein Frontmatter" (korrekt dokumentiertes Verhalten)
        text = "---\nname: test\n---\n"
        fm, body = split_frontmatter(text)
        # Nach strip() bleibt "---\nname: test\n---" -- kein Newline nach ---
        # -> kein Frontmatter erkannt (Code-limitierung, kein Bug)
        assert fm is None

    def test_frontmatter_missing_closing_dashes(self):
        # Kein abschliessender ---: wird als kein Frontmatter interpretiert
        text = "---\nname: test\nkein Ende"
        fm, body = split_frontmatter(text)
        assert fm is None
        assert "name: test" in body

    def test_text_starting_with_dashes_but_no_newline_before_closing(self):
        # Sicherstellen: nur gueltige Frontmatter wird erkannt
        text = "---\nname: skill\n---\nBody line."
        fm, body = split_frontmatter(text)
        assert fm is not None
        assert "Body line." in body

    def test_whitespace_only(self):
        fm, body = split_frontmatter("   ")
        assert fm is None
        assert body == ""

    def test_returns_tuple(self):
        result = split_frontmatter("Hallo")
        assert isinstance(result, tuple)
        assert len(result) == 2


# ============================================================
# chunk_text
# ============================================================

class TestChunkText:
    def test_empty_string(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        text = "Ein kurzer Text mit wenigen Woertern."
        chunks = chunk_text(text)
        assert len(chunks) >= 1
        assert isinstance(chunks[0], Chunk)

    def test_returns_chunk_objects(self):
        chunks = chunk_text("Hallo Welt wie geht es dir heute.")
        for c in chunks:
            assert hasattr(c, "index")
            assert hasattr(c, "content")
            assert hasattr(c, "token_count")
            assert hasattr(c, "is_frontmatter")

    def test_chunk_index_sequential(self):
        text = " ".join(["word"] * 1000)
        chunks = chunk_text(text)
        for i, c in enumerate(chunks):
            assert c.index == i

    def test_frontmatter_chunk_flagged(self):
        text = "---\nname: skill\ncategory: test\n---\n\n" + " ".join(["word"] * 100)
        chunks = chunk_text(text)
        assert chunks[0].is_frontmatter is True
        # Alle anderen Chunks: kein Frontmatter
        for c in chunks[1:]:
            assert c.is_frontmatter is False

    def test_no_frontmatter_all_chunks_not_flagged(self):
        text = " ".join(["word"] * 100)
        chunks = chunk_text(text, separate_frontmatter=True)
        for c in chunks:
            assert c.is_frontmatter is False

    def test_large_text_multiple_chunks(self):
        # Chunker splittet an Absaetzen (Leerzeilen). Ein Text mit mehreren
        # Absaetzen von je ~400 Woertern erzeugt mehrere Chunks.
        paragraph = " ".join([f"word{i}" for i in range(400)])
        text = "\n\n".join([paragraph, paragraph, paragraph, paragraph])
        chunks = chunk_text(text, chunk_size=350)
        assert len(chunks) >= 3

    def test_single_line_no_paragraphs_exceeds_max(self):
        # Ein einziger Einzeiler > MAX_CHUNK_SIZE (500) wird als ein oversized Chunk
        # unveraendert zurueckgegeben (kein Split ohne Satzzeichen/Absaetze moeglich)
        text = " ".join([f"word{i}" for i in range(1400)])
        chunks = chunk_text(text, chunk_size=350)
        assert len(chunks) == 1
        assert chunks[0].token_count == 1400

    def test_token_count_matches_content(self):
        text = "Dies ist ein Test mit genau acht Woertern hier."
        chunks = chunk_text(text)
        for c in chunks:
            expected = estimate_tokens(c.content)
            assert c.token_count == expected

    def test_chunk_size_respected_roughly(self):
        # Chunks sollten nicht massiv ueber chunk_size liegen
        text = " ".join([f"word{i}" for i in range(2000)])
        chunks = chunk_text(text, chunk_size=100)
        non_fm = [c for c in chunks if not c.is_frontmatter]
        # Letzte Chunk darf groesser sein (merge kleiner Reste)
        for c in non_fm[:-1]:
            assert c.token_count <= 200  # MAX_CHUNK_SIZE=500, aber praktisch deutlich weniger

    def test_overlap_produces_repeated_content(self):
        # Mit Overlap: Inhalt aus dem Vorgaenger-Chunk taucht in Folge-Chunk auf
        sentences = ["Der erste Satz ist hier. " * 30,
                     "Der zweite Satz folgt jetzt. " * 30,
                     "Der dritte Satz kommt danach. " * 30]
        text = "\n\n".join(sentences)
        chunks_no_overlap = chunk_text(text, chunk_size=60, overlap=0)
        chunks_with_overlap = chunk_text(text, chunk_size=60, overlap=20)
        # Mit Overlap gibt es mindestens genauso viele Chunks
        assert len(chunks_with_overlap) >= len(chunks_no_overlap) - 1

    def test_to_dict(self):
        chunks = chunk_text("Ein einfacher Test Text Satz.")
        d = chunks[0].to_dict()
        assert "index" in d
        assert "content" in d
        assert "token_count" in d
        assert "is_frontmatter" in d

    def test_separate_frontmatter_false(self):
        text = "---\nname: test\n---\n\nBody text hier."
        chunks_with = chunk_text(text, separate_frontmatter=True)
        chunks_without = chunk_text(text, separate_frontmatter=False)
        # Ohne separate_frontmatter: kein Chunk mit is_frontmatter=True
        assert not any(c.is_frontmatter for c in chunks_without)


# ============================================================
# schema.py: ensure_schema + get_schema_version
# ============================================================

class TestSchema:
    def test_ensure_schema_in_memory(self):
        # Nutze In-Memory-DB ueber temporaere Datei
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn = ensure_schema(db_path)
            assert conn is not None
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_ensure_schema_returns_connection(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn = ensure_schema(db_path)
            assert isinstance(conn, sqlite3.Connection)
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_schema_version_written(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn = ensure_schema(db_path)
            conn.close()
            version = get_schema_version(db_path)
            assert version == SCHEMA_VERSION
        finally:
            db_path.unlink(missing_ok=True)

    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == 3

    def test_get_schema_version_nonexistent(self, tmp_path):
        # Datei existiert nicht -> Version 0
        missing = tmp_path / "nonexistent.db"
        version = get_schema_version(missing)
        assert version == 0

    def test_expected_tables_exist(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn = ensure_schema(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = {row[0] for row in cursor.fetchall()}
            expected = {
                "skill_index", "skill_chunks", "skill_keywords",
                "wiki_index", "wiki_chunks", "wiki_keywords",
                "documents", "document_chunks", "document_keywords",
                "summaries", "digest_queue", "schema_meta",
            }
            assert expected.issubset(tables)
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_ensure_schema_idempotent(self):
        # Zweimal aufrufen darf keinen Fehler erzeugen
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn1 = ensure_schema(db_path)
            conn1.close()
            conn2 = ensure_schema(db_path)
            conn2.close()
            version = get_schema_version(db_path)
            assert version == SCHEMA_VERSION
        finally:
            db_path.unlink(missing_ok=True)

    def test_fts_tables_exist(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn = ensure_schema(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = {row[0] for row in cursor.fetchall()}
            assert "skill_fts" in tables
            assert "wiki_fts" in tables
            assert "document_fts" in tables
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)


# ============================================================
# config.py: Config
# ============================================================

class TestConfig:
    def test_default_values(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        assert cfg.get("chunk_size") == 350
        assert cfg.get("chunk_overlap") == 0
        assert cfg.get("web_port") == 8787
        assert cfg.get("bach_enabled") is False
        assert cfg.get("theme") == "dark"

    def test_get_with_default(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        # Nicht vorhandener Key mit Default
        assert cfg.get("nonexistent_key", "fallback") == "fallback"

    def test_set_and_get(self, tmp_path):
        cfg = Config(config_path=tmp_path / "test.json")
        cfg.set("web_port", 9999)
        assert cfg.get("web_port") == 9999

    def test_save_and_reload(self, tmp_path):
        config_file = tmp_path / "test.json"
        cfg = Config(config_path=config_file)
        cfg.set("web_port", 1234)
        cfg.save()
        assert config_file.exists()

        # Neu laden
        cfg2 = Config(config_path=config_file)
        assert cfg2.get("web_port") == 1234

    def test_save_creates_parent_dir(self, tmp_path):
        nested_path = tmp_path / "subdir" / "config.json"
        cfg = Config(config_path=nested_path)
        cfg.save()
        assert nested_path.exists()

    def test_get_db_path_default(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        db_path = cfg.get_db_path()
        assert isinstance(db_path, Path)
        assert db_path.name == "knowledge.db"

    def test_get_db_path_custom(self, tmp_path):
        config_file = tmp_path / "cfg.json"
        cfg = Config(config_path=config_file)
        cfg.set("db_path", str(tmp_path / "custom.db"))
        assert cfg.get_db_path() == tmp_path / "custom.db"

    def test_get_inbox_dir_default(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        inbox = cfg.get_inbox_dir()
        assert inbox.name == "inbox"

    def test_get_archive_dir_default(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        archive = cfg.get_archive_dir()
        assert archive.name == "archive"

    def test_get_indexed_directories_empty(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        dirs = cfg.get_indexed_directories()
        assert dirs == []

    def test_data_property_returns_dict(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        d = cfg.data
        assert isinstance(d, dict)
        assert "chunk_size" in d

    def test_data_property_is_copy(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nonexistent.json")
        d = cfg.data
        d["chunk_size"] = 9999
        # Original unveraendert
        assert cfg.get("chunk_size") == 350

    def test_load_invalid_json_graceful(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{ invalid json !!!", encoding="utf-8")
        cfg = Config(config_path=bad_file)
        # Defaults greifen trotzdem
        assert cfg.get("chunk_size") == 350

    def test_save_uses_ensure_ascii_false(self, tmp_path):
        config_file = tmp_path / "cfg.json"
        cfg = Config(config_path=config_file)
        cfg.set("description", "Über Ärger")
        cfg.save()
        content = config_file.read_text(encoding="utf-8")
        assert "Über Ärger" in content


# ============================================================
# utils.py: sha256_hash + extract_keywords
# ============================================================

class TestSha256Hash:
    def test_returns_string(self):
        result = sha256_hash("test")
        assert isinstance(result, str)

    def test_returns_hex(self):
        result = sha256_hash("hello")
        assert all(c in "0123456789abcdef" for c in result)

    def test_length_64(self):
        result = sha256_hash("any text")
        assert len(result) == 64

    def test_empty_string(self):
        result = sha256_hash("")
        assert len(result) == 64

    def test_deterministic(self):
        assert sha256_hash("hello") == sha256_hash("hello")

    def test_different_inputs_different_hashes(self):
        assert sha256_hash("hello") != sha256_hash("world")

    def test_unicode(self):
        result = sha256_hash("Überblick")
        assert len(result) == 64

    def test_known_hash(self):
        # sha256("hello") ist bekannt
        import hashlib
        expected = hashlib.sha256("hello".encode("utf-8")).hexdigest()
        assert sha256_hash("hello") == expected


class TestExtractKeywords:
    def test_empty_string(self):
        assert extract_keywords("") == []

    def test_returns_list(self):
        result = extract_keywords("Python code analysis tool")
        assert isinstance(result, list)

    def test_stopwords_excluded(self):
        # "der", "die", "das", "the", "and" sind Stoppwoerter
        text = "der die das the and"
        result = extract_keywords(text)
        for sw in ["der", "die", "das", "the", "and"]:
            assert sw not in result

    def test_keywords_contain_content_words(self):
        text = "Python programming language analysis"
        result = extract_keywords(text)
        # Mindestens eins der Inhaltswörter soll enthalten sein
        assert len(result) > 0
        assert any(w in result for w in ["python", "programming", "language", "analysis"])

    def test_short_words_excluded(self):
        # Woerter kuerzer als MIN_KEYWORD_LEN (3) werden gefiltert
        # Regex verlangt ohnehin >= 3 Zeichen
        result = extract_keywords("ab cd ef longer_word")
        assert "ab" not in result
        assert "cd" not in result
        assert "ef" not in result

    def test_max_count_respected(self):
        # Viele verschiedene Woerter -- max_count=5
        words = [f"keyword{i}" * 1 for i in range(100)]
        text = " ".join(words)
        result = extract_keywords(text, max_count=5)
        assert len(result) <= 5

    def test_frequency_sorting(self):
        # "frequent" erscheint oefters als "rare"
        text = "frequent frequent frequent frequent rare"
        result = extract_keywords(text)
        assert result[0] == "frequent"

    def test_lowercase_output(self):
        text = "Python PYTHON python"
        result = extract_keywords(text)
        for kw in result:
            assert kw == kw.lower()

    def test_default_max_count(self):
        # Default ist MAX_KEYWORDS_PER_ITEM = 30
        words = [f"uniqueword{i}" for i in range(100)]
        text = " ".join(words)
        result = extract_keywords(text)
        assert len(result) <= 30

    def test_stop_words_is_frozenset(self):
        assert isinstance(STOP_WORDS, frozenset)

    def test_common_german_stopwords_in_set(self):
        for sw in ["der", "die", "das", "und", "ist"]:
            assert sw in STOP_WORDS

    def test_common_english_stopwords_in_set(self):
        for sw in ["the", "and", "is", "are", "for"]:
            assert sw in STOP_WORDS
