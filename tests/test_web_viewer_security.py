# -*- coding: utf-8 -*-
"""Sicherheitstests fuer den Web-Viewer (Review 2026-07-04).

Vorher: do_POST delegierte an do_GET — ein einfaches <img src>-GET konnte
Dateien loeschen (CSRF ohne POST); kein Host-Check (DNS-Rebinding); das
FTS5-Suchsnippet wurde unescaped gerendert (Stored XSS).
"""
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema import ensure_schema  # noqa: E402
from web_viewer import ViewerHandler, page_search  # noqa: E402


def _make_db(tmpdir):
    db = Path(tmpdir) / "knowledge.db"
    conn = ensure_schema(db)
    conn.execute(
        "INSERT INTO documents (id, filename, file_path, file_type, word_count) "
        "VALUES (1, 'evil.html', ?, 'html', 5)",
        (str(Path(tmpdir) / "evil.html"),),
    )
    conn.execute(
        "INSERT INTO document_chunks (id, doc_id, chunk_index, content) "
        "VALUES (1, 1, 0, 'harmlos <script>alert(1)</script> suchwort ende')",
    )
    conn.commit()
    conn.close()
    return db


class _Server:
    def __init__(self, db_path):
        handler = type("H", (ViewerHandler,), {"db_path": str(db_path)})
        self.httpd = HTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def request(self, path, method="GET", headers=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method,
            data=b"" if method == "POST" else None)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestWebViewerSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = _make_db(cls.tmp.name)
        cls.srv = _Server(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        cls.tmp.cleanup()

    def test_get_on_destructive_route_is_405(self):
        for route in ("/api/delete_file/1", "/api/reset_doc/1", "/open/1"):
            status, body = self.srv.request(route)
            self.assertEqual(status, 405, route)
            self.assertIn("POST required", body)

    def test_get_with_evil_host_is_403(self):
        status, body = self.srv.request("/", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 403)
        self.assertIn("Forbidden host", body)

    def test_post_with_evil_origin_is_403(self):
        status, body = self.srv.request(
            "/api/reset_doc/1", method="POST",
            headers={"Origin": "http://evil.example.com"})
        self.assertEqual(status, 403)
        self.assertIn("Forbidden origin", body)

    def test_post_reset_with_local_origin_works(self):
        status, body = self.srv.request(
            "/api/reset_doc/1", method="POST",
            headers={"Origin": f"http://127.0.0.1:{self.srv.port}"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_post_without_origin_works(self):
        # curl/CLI-Kompatibilitaet: lokale Tools senden keinen Origin-Header;
        # Browser senden bei Cross-Origin-POSTs dagegen immer einen.
        status, body = self.srv.request("/api/reset_doc/1", method="POST")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_document_still_present_after_blocked_requests(self):
        conn = sqlite3.connect(str(self.db))
        n = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        conn.close()
        self.assertEqual(n, 1)

    def test_search_snippet_escapes_html(self):
        html = page_search(str(self.db), query="suchwort")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
