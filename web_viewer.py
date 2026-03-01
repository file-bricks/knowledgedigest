# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Web-Viewer (stdlib-only).

Startet einen lokalen Webserver mit Dashboard, Browse und Suche.
Nutzt nur Python-Stdlib (kein Flask/Django noetig).
Adaptiert von Wissensdatenbank viewer.py.

Usage:
    python -m KnowledgeDigest --web              # Default Port 8787
    python -m KnowledgeDigest --web --port 9000   # Custom Port
"""

import os
import sys
import json
import html
import sqlite3
import argparse
import webbrowser
import urllib.parse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path


def _get_conn(db_path):
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _esc(text):
    return html.escape(str(text)) if text else ""


# ============================================================
# CSS + Layout
# ============================================================

_CSS = """
:root { --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
    --text2: #8b949e; --accent: #58a6ff; --green: #3fb950; --orange: #d29922; --red: #f85149; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text);
    line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; }
a { color: var(--accent); text-decoration: none; } a:hover { text-decoration: underline; }
h1 { font-size: 1.6em; margin-bottom: 8px; }
h2 { font-size: 1.2em; color: var(--text2); margin: 20px 0 10px; }
.nav { display: flex; gap: 20px; padding: 12px 0; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
.nav a { font-weight: 600; padding: 4px 12px; border-radius: 6px; }
.nav a.active, .nav a:hover { background: var(--surface); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px; margin-bottom: 12px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.stat-card { text-align: center; }
.stat-card .num { font-size: 2em; font-weight: 700; color: var(--accent); }
.stat-card .label { color: var(--text2); font-size: 0.85em; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
th { color: var(--text2); font-size: 0.85em; text-transform: uppercase; }
tr:hover { background: rgba(88,166,255,0.04); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }
.badge-green { background: rgba(63,185,80,0.15); color: var(--green); }
.badge-orange { background: rgba(210,153,34,0.15); color: var(--orange); }
.badge-blue { background: rgba(88,166,255,0.15); color: var(--accent); }
.search-box { display: flex; gap: 8px; margin-bottom: 20px; }
.search-box input { flex: 1; padding: 10px 14px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: 1em; }
.search-box button { padding: 10px 20px; background: var(--accent); color: #fff; border: none;
    border-radius: 6px; cursor: pointer; font-weight: 600; }
.summary-text { color: var(--text); line-height: 1.5; margin: 8px 0; }
.kw { color: var(--text2); font-size: 0.85em; }
.domain-tag { display: inline-block; padding: 2px 8px; background: rgba(88,166,255,0.1);
    color: var(--accent); border-radius: 4px; font-size: 0.8em; margin-right: 4px; }
.pager { display: flex; gap: 8px; justify-content: center; margin-top: 16px; }
.pager a { padding: 6px 14px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; }
.progress-bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; margin-top: 8px; }
.progress-fill { height: 100%; background: var(--green); border-radius: 4px; transition: width 0.3s; }
"""

_HEAD = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KnowledgeDigest</title><style>{css}</style></head><body>
<h1>KnowledgeDigest</h1>
<nav class="nav">
<a href="/" {nav_dash}>Dashboard</a>
<a href="/summaries" {nav_sum}>Summaries</a>
<a href="/browse" {nav_browse}>Browse</a>
<a href="/search" {nav_search}>Suche</a>
<a href="/folders" {nav_folders}>Ordner</a>
</nav>"""

_FOOT = """<hr style="border-color:var(--border);margin:30px 0 10px">
<p style="color:var(--text2);font-size:0.8em;text-align:center">
KnowledgeDigest | {docs} Dokumente | {summaries} Summaries</p></body></html>"""


def _layout(body, active="dash", db_path=None):
    conn = _get_conn(db_path)
    docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    sums = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
    conn.close()
    navs = {"nav_dash": "", "nav_sum": "", "nav_browse": "", "nav_search": "", "nav_folders": ""}
    key = {"dash": "nav_dash", "sum": "nav_sum", "browse": "nav_browse",
           "search": "nav_search", "folders": "nav_folders"}.get(active, "nav_dash")
    navs[key] = 'class="active"'
    head = _HEAD.format(css=_CSS, **navs)
    foot = _FOOT.format(docs=f"{docs:,}", summaries=f"{sums:,}")
    return head + body + foot


# ============================================================
# Pages
# ============================================================

def page_dashboard(db_path):
    conn = _get_conn(db_path)
    docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
    words = conn.execute("SELECT COALESCE(SUM(word_count),0) FROM documents").fetchone()[0]
    sums = conn.execute("SELECT COUNT(*) FROM summaries WHERE source_type='document'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM digest_queue WHERE status='pending'").fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM digest_queue WHERE status='done'").fetchone()[0]
    pct = round(done / max(docs, 1) * 100, 1)

    by_type = conn.execute(
        "SELECT file_type, COUNT(*) as cnt, SUM(word_count) as words "
        "FROM documents GROUP BY file_type ORDER BY cnt DESC"
    ).fetchall()

    domains = conn.execute(
        "SELECT domain, COUNT(*) as cnt FROM summaries "
        "WHERE domain != '' GROUP BY domain ORDER BY cnt DESC LIMIT 15"
    ).fetchall()

    recent = conn.execute(
        "SELECT s.source_id, d.filename, s.domain, s.summary, s.created_at "
        "FROM summaries s JOIN documents d ON d.id = s.source_id "
        "WHERE s.source_type='document' ORDER BY s.created_at DESC LIMIT 5"
    ).fetchall()
    conn.close()

    body = f"""
    <div class="stat-grid">
        <div class="card stat-card"><div class="num">{docs:,}</div><div class="label">Dokumente</div></div>
        <div class="card stat-card"><div class="num">{chunks:,}</div><div class="label">Chunks</div></div>
        <div class="card stat-card"><div class="num">{words:,}</div><div class="label">Woerter</div></div>
        <div class="card stat-card"><div class="num">{sums:,}</div><div class="label">Summaries</div></div>
    </div>
    <h2>Summarization Fortschritt</h2>
    <div class="card">
        <div style="display:flex;justify-content:space-between">
            <span>{done:,} / {docs:,} Dokumente</span>
            <span style="color:var(--green);font-weight:700">{pct}%</span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:{pct}%"></div></div>
        <div style="margin-top:8px;color:var(--text2);font-size:0.85em">
            <span class="badge badge-green">{done:,} done</span>
            <span class="badge badge-orange">{pending:,} pending</span>
        </div>
    </div>
    <h2>Dateitypen</h2>
    <div class="card"><table><tr><th>Typ</th><th>Dateien</th><th>Woerter</th></tr>"""

    for r in by_type:
        w = r["words"] or 0
        body += f'<tr><td><span class="badge badge-blue">{_esc(r["file_type"])}</span></td>'
        body += f'<td>{r["cnt"]:,}</td><td>{w:,}</td></tr>'
    body += "</table></div>"

    if domains:
        body += '<h2>Domains (Top 15)</h2><div class="card"><table><tr><th>Domain</th><th>Summaries</th></tr>'
        for r in domains:
            body += f'<tr><td><span class="domain-tag">{_esc(r["domain"])}</span></td><td>{r["cnt"]}</td></tr>'
        body += "</table></div>"

    if recent:
        body += '<h2>Letzte Summaries</h2>'
        for r in recent:
            body += f"""<div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <a href="/doc/{r['source_id']}"><strong>{_esc(r['filename'])}</strong></a>
                    <span class="domain-tag">{_esc(r['domain'])}</span>
                </div>
                <p class="summary-text">{_esc(r['summary'][:200])}</p>
                <span style="color:var(--text2);font-size:0.8em">{_esc(r['created_at'])}</span>
            </div>"""

    return _layout(body, "dash", db_path)


def page_summaries(db_path, page=1, per_page=25):
    conn = _get_conn(db_path)
    offset = (page - 1) * per_page
    total = conn.execute("SELECT COUNT(*) FROM summaries WHERE source_type='document'").fetchone()[0]
    rows = conn.execute(
        "SELECT s.source_id, s.chunk_index, d.filename, s.summary, s.keywords, s.domain, s.model, s.created_at "
        "FROM summaries s JOIN documents d ON d.id = s.source_id "
        "WHERE s.source_type='document' ORDER BY s.created_at DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)
    body = f'<h2>Summaries ({total:,} gesamt, Seite {page}/{total_pages})</h2>'
    for r in rows:
        kws = r["keywords"] or ""
        body += f"""<div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <a href="/doc/{r['source_id']}"><strong>{_esc(r['filename'])}</strong></a>
                <span class="domain-tag">{_esc(r['domain'])}</span>
            </div>
            <p class="summary-text">{_esc(r['summary'])}</p>
            <div class="kw">Keywords: {_esc(kws)} | Model: {_esc(r['model'])} | {_esc(r['created_at'])}</div>
        </div>"""

    body += '<div class="pager">'
    if page > 1:
        body += f'<a href="/summaries?page={page-1}">&laquo; Zurueck</a>'
    if page < total_pages:
        body += f'<a href="/summaries?page={page+1}">Weiter &raquo;</a>'
    body += '</div>'
    return _layout(body, "sum", db_path)


def page_browse(db_path, page=1, per_page=50):
    conn = _get_conn(db_path)
    offset = (page - 1) * per_page
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    rows = conn.execute(
        "SELECT d.id, d.filename, d.file_type, d.word_count, d.chunk_count, "
        "(SELECT COUNT(*) FROM summaries s WHERE s.source_type='document' AND s.source_id=d.id) as sum_count "
        "FROM documents d ORDER BY d.filename LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)
    body = f'<h2>Dokumente ({total:,} gesamt, Seite {page}/{total_pages})</h2>'
    body += '<div class="card"><table><tr><th>Datei</th><th>Typ</th><th>Woerter</th><th>Chunks</th><th>Summaries</th></tr>'
    for r in rows:
        badge = '<span class="badge badge-green">done</span>' if r["sum_count"] > 0 else '<span class="badge badge-orange">pending</span>'
        body += f'<tr><td><a href="/doc/{r["id"]}">{_esc(r["filename"])}</a></td>'
        body += f'<td><span class="badge badge-blue">{_esc(r["file_type"])}</span></td>'
        body += f'<td>{r["word_count"]:,}</td><td>{r["chunk_count"]}</td><td>{badge}</td></tr>'
    body += '</table></div>'

    body += '<div class="pager">'
    if page > 1:
        body += f'<a href="/browse?page={page-1}">&laquo; Zurueck</a>'
    if page < total_pages:
        body += f'<a href="/browse?page={page+1}">Weiter &raquo;</a>'
    body += '</div>'
    return _layout(body, "browse", db_path)


def page_doc(db_path, doc_id):
    conn = _get_conn(db_path)
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return _layout('<div class="card">Dokument nicht gefunden.</div>', "browse", db_path)

    chunks = conn.execute(
        "SELECT chunk_index, content, token_count FROM document_chunks WHERE doc_id=? ORDER BY chunk_index",
        (doc_id,)
    ).fetchall()
    sums = conn.execute(
        "SELECT chunk_index, summary, keywords, domain, model, created_at FROM summaries "
        "WHERE source_type='document' AND source_id=? ORDER BY chunk_index",
        (doc_id,)
    ).fetchall()
    sum_map = {s["chunk_index"]: s for s in sums}
    kws = conn.execute(
        "SELECT keyword, source FROM document_keywords WHERE doc_id=? ORDER BY source, keyword",
        (doc_id,)
    ).fetchall()
    conn.close()

    body = f"""<h2>{_esc(doc['filename'])}</h2>
    <div class="card"><table>
        <tr><td style="color:var(--text2)">Pfad</td><td style="font-size:0.85em">
            <a href="#" onclick="openFile({doc_id}); return false;"
               style="cursor:pointer" title="Datei oeffnen">{_esc(doc['file_path'])}</a></td></tr>
        <tr><td style="color:var(--text2)">Typ</td><td><span class="badge badge-blue">{_esc(doc['file_type'])}</span></td></tr>
        <tr><td style="color:var(--text2)">Woerter</td><td>{doc['word_count']:,}</td></tr>
        <tr><td style="color:var(--text2)">Chunks</td><td>{doc['chunk_count']}</td></tr>
        <tr><td style="color:var(--text2)">Indexiert</td><td>{_esc(doc['ingested_at'])}</td></tr>
    </table>
    <div style="margin-top:12px">
        <a href="#" onclick="openFile({doc_id}); return false;"
           style="display:inline-block;padding:8px 16px;background:var(--accent);color:#fff;
           border-radius:6px;font-weight:600;cursor:pointer;text-decoration:none">Datei oeffnen</a>
    </div></div>
    <script>
    function openFile(docId) {{
        fetch('/open/' + docId).then(r => r.json())
            .then(data => {{ if (!data.ok) alert('Fehler: ' + data.error); }})
            .catch(e => alert('Fehler: ' + e));
    }}
    </script>"""

    if kws:
        body += '<h2>Keywords</h2><div class="card">'
        for kw in kws:
            cls = "badge-blue" if kw["source"] == "content" else "badge-orange"
            body += f'<span class="badge {cls}" style="margin:2px">{_esc(kw["keyword"])}</span> '
        body += '</div>'

    body += '<h2>Chunks & Summaries</h2>'
    for ch in chunks:
        ci = ch["chunk_index"]
        s = sum_map.get(ci)
        body += f"""<div class="card">
            <div style="display:flex;justify-content:space-between">
                <strong>Chunk {ci}</strong>
                <span style="color:var(--text2);font-size:0.85em">{ch['token_count']} tokens</span>
            </div>
            <pre style="white-space:pre-wrap;color:var(--text2);font-size:0.85em;margin:8px 0;
                max-height:200px;overflow-y:auto">{_esc(ch['content'][:1000])}</pre>"""
        if s:
            body += f"""<div style="border-top:1px solid var(--border);padding-top:8px;margin-top:8px">
                <span class="domain-tag">{_esc(s['domain'])}</span>
                <span class="badge badge-green">summarized</span>
                <span style="color:var(--text2);font-size:0.8em">({_esc(s['model'])})</span>
                <p class="summary-text" style="margin-top:6px">{_esc(s['summary'])}</p>
                <div class="kw">Keywords: {_esc(s['keywords'])}</div>
            </div>"""
        else:
            body += '<div style="margin-top:8px"><span class="badge badge-orange">no summary</span></div>'
        body += '</div>'

    return _layout(body, "browse", db_path)


def page_search(db_path, query="", limit=30):
    body = f"""<h2>Volltextsuche</h2>
    <form class="search-box" method="get" action="/search">
        <input type="text" name="q" value="{_esc(query)}" placeholder="Suchbegriff eingeben...">
        <button type="submit">Suchen</button>
    </form>"""
    if query:
        conn = _get_conn(db_path)
        try:
            rows = conn.execute(
                "SELECT d.id, d.filename, d.file_type, d.word_count, "
                "snippet(document_fts, 1, '<mark>', '</mark>', '...', 30) as snippet "
                "FROM document_fts JOIN document_chunks dc ON document_fts.rowid = dc.id "
                "JOIN documents d ON dc.doc_id = d.id "
                "WHERE document_fts MATCH ? ORDER BY document_fts.rank LIMIT ?",
                (query, limit)
            ).fetchall()
        except Exception:
            like = f"%{query}%"
            rows = conn.execute(
                "SELECT DISTINCT d.id, d.filename, d.file_type, d.word_count, '' as snippet "
                "FROM documents d LEFT JOIN document_chunks dc ON dc.doc_id = d.id "
                "WHERE dc.content LIKE ? OR d.filename LIKE ? LIMIT ?",
                (like, like, limit)
            ).fetchall()
        conn.close()

        if rows:
            seen = set()
            body += f'<p style="color:var(--text2)">{len(rows)} Treffer</p>'
            for r in rows:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                snippet = r["snippet"] or ""
                body += f"""<div class="card">
                    <a href="/doc/{r['id']}"><strong>{_esc(r['filename'])}</strong></a>
                    <span class="badge badge-blue" style="margin-left:8px">{_esc(r['file_type'])}</span>
                    <span style="color:var(--text2);margin-left:8px">{r['word_count']:,} Woerter</span>
                    <p style="font-size:0.9em;margin-top:6px">{snippet}</p>
                </div>"""
        else:
            body += '<div class="card">Keine Treffer.</div>'

    return _layout(body, "search", db_path)


def page_folders(db_path):
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT source_dir, COUNT(*) as cnt, SUM(word_count) as words, "
        "SUM(CASE WHEN id IN (SELECT source_id FROM summaries WHERE source_type='document') THEN 1 ELSE 0 END) as sum_cnt "
        "FROM documents GROUP BY source_dir ORDER BY cnt DESC"
    ).fetchall()
    conn.close()

    body = '<h2>Ordner</h2>'
    body += '<div class="card"><table><tr><th>Ordner</th><th>Dateien</th><th>Woerter</th><th>Summaries</th><th>%</th></tr>'
    for r in rows:
        cnt = r["cnt"]
        sc = r["sum_cnt"]
        pct = round(sc / max(cnt, 1) * 100)
        folder = r["source_dir"] or "(root)"
        words = r["words"] or 0
        color = "var(--green)" if pct == 100 else "var(--orange)" if pct > 0 else "var(--text2)"
        body += f"""<tr>
            <td title="{_esc(folder)}">{_esc(folder[:80])}</td>
            <td>{cnt}</td><td>{words:,}</td><td>{sc}/{cnt}</td>
            <td style="color:{color};font-weight:600">{pct}%</td>
        </tr>"""
    body += '</table></div>'
    return _layout(body, "folders", db_path)


# ============================================================
# HTTP Handler
# ============================================================

class ViewerHandler(BaseHTTPRequestHandler):
    db_path = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/" or path == "":
                content = page_dashboard(self.db_path)
            elif path == "/summaries":
                pg = int(params.get("page", [1])[0])
                content = page_summaries(self.db_path, page=pg)
            elif path == "/browse":
                pg = int(params.get("page", [1])[0])
                content = page_browse(self.db_path, page=pg)
            elif path.startswith("/doc/"):
                doc_id = int(path.split("/doc/")[1])
                content = page_doc(self.db_path, doc_id)
            elif path == "/search":
                q = params.get("q", [""])[0]
                content = page_search(self.db_path, query=q)
            elif path == "/folders":
                content = page_folders(self.db_path)
            elif path == "/api/status":
                content = self._api_status()
                self._respond(200, content, "application/json")
                return
            elif path.startswith("/open/"):
                doc_id = int(path.split("/open/")[1])
                result = self._open_file(doc_id)
                self._respond(200, json.dumps(result), "application/json")
                return
            else:
                content = _layout('<div class="card">404 - Seite nicht gefunden</div>', "dash", self.db_path)
            self._respond(200, content)
        except Exception as e:
            content = _layout(f'<div class="card" style="color:var(--red)">Fehler: {_esc(str(e))}</div>',
                              "dash", self.db_path)
            self._respond(500, content)

    def _open_file(self, doc_id):
        conn = _get_conn(self.db_path)
        row = conn.execute("SELECT file_path FROM documents WHERE id=?", (doc_id,)).fetchone()
        conn.close()
        if not row:
            return {"ok": False, "error": "Dokument nicht gefunden"}
        file_path = row["file_path"]
        p = Path(file_path)
        if not p.exists():
            return {"ok": False, "error": f"Datei nicht gefunden: {file_path}"}
        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            else:
                import subprocess
                subprocess.run(["xdg-open", str(p)])
            return {"ok": True, "path": file_path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_status(self):
        conn = _get_conn(self.db_path)
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        sums = conn.execute("SELECT COUNT(*) FROM summaries WHERE source_type='document'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM digest_queue WHERE status='pending'").fetchone()[0]
        conn.close()
        return json.dumps({"documents": docs, "summaries": sums, "pending": pending})

    def _respond(self, status, content, content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        data = content.encode("utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


# ============================================================
# Server Start
# ============================================================

def start_server_thread(db_path, port=8787):
    """Startet den Web-Viewer in einem Daemon-Thread. Gibt den Server zurueck."""
    ViewerHandler.db_path = Path(db_path)
    server = HTTPServer(("127.0.0.1", port), ViewerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def launch_web():
    """CLI-Entry-Point fuer den Web-Viewer."""
    # Config laden
    sys.path.insert(0, str(Path(__file__).parent))
    from config import get_config
    cfg = get_config()

    parser = argparse.ArgumentParser(description="KnowledgeDigest Web-Viewer")
    parser.add_argument("--port", "-p", type=int, default=cfg.get("web_port", 8787))
    parser.add_argument("--db", type=str, default=str(cfg.get_db_path()))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    ViewerHandler.db_path = Path(args.db)
    server = HTTPServer(("127.0.0.1", args.port), ViewerHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"KnowledgeDigest Web-Viewer: {url}")
    print(f"DB: {args.db}")
    print("Stoppen mit Ctrl+C")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nViewer beendet.")
        server.server_close()
    return 0
