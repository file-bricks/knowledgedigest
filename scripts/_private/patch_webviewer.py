#!/usr/bin/env python3
"""Patcht web_viewer.py: File-Download statt xdg-open."""
from pathlib import Path

path = Path('/opt/knowledgedigest/web_viewer.py')
content = path.read_text(encoding='utf-8')

# 1. Replace _open_file method
old_method = '''    def _open_file(self, doc_id):
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
            return {"ok": False, "error": str(e)}'''

new_method = '''    def _open_file(self, doc_id):
        """Gibt Datei-Pfad zurueck fuer Download/Preview."""
        conn = _get_conn(self.db_path)
        row = conn.execute("SELECT file_path, filename, file_type FROM documents WHERE id=?", (doc_id,)).fetchone()
        conn.close()
        if not row:
            return None, None, "Dokument nicht gefunden"
        file_path = row["file_path"]
        p = Path(file_path)
        if not p.exists():
            return None, None, f"Datei nicht gefunden: {file_path}"
        return p, row["filename"], None'''

if old_method in content:
    content = content.replace(old_method, new_method)
    print("[OK] _open_file ersetzt")
else:
    print("[SKIP] _open_file nicht gefunden (evtl. schon gepatcht)")

# 2. Replace /open/ handler
old_handler = '''            elif path.startswith("/open/"):
                doc_id = int(path.split("/open/")[1])
                result = self._open_file(doc_id)
                self._respond(200, json.dumps(result), "application/json")
                return'''

new_handler = '''            elif path.startswith("/open/"):
                doc_id = int(path.split("/open/")[1])
                filepath, filename, error = self._open_file(doc_id)
                if error:
                    self._respond(404, json.dumps({"ok": False, "error": error}), "application/json")
                else:
                    data = filepath.read_bytes()
                    mime_map = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8",
                                ".md": "text/plain; charset=utf-8", ".html": "text/html",
                                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
                    mime = mime_map.get(filepath.suffix.lower(), "application/octet-stream")
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Disposition", f'inline; filename="{filename}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                return'''

if old_handler in content:
    content = content.replace(old_handler, new_handler)
    print("[OK] /open/ Handler ersetzt")
else:
    print("[SKIP] /open/ Handler nicht gefunden")

path.write_text(content, encoding='utf-8')
print("[DONE] web_viewer.py gepatcht")
