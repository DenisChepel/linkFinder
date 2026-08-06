#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py - web interface for the site link finder.

Run:
    python app.py
A browser opens at http://127.0.0.1:8765

Built on the standard library - no Flask or Django needed.
Front-end lives in static/ (index.html + css/ + js/).
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import core

# Shown in the interface header. If it does not change after a code update,
# the server is still running the old code and needs a restart.
VERSION = "3.6"

HOST = "127.0.0.1"
PORT = 8765

# The app can run either from source or from a PyInstaller .exe, and the two
# need different paths: bundled files live in a temporary folder that is wiped
# on exit, so reports must never be written there.
FROZEN = getattr(sys, "frozen", False)

#: where static/ lives - inside the bundle when frozen
APP_DIR = sys._MEIPASS if FROZEN else os.path.dirname(os.path.abspath(__file__))

#: where reports are written - next to the .exe, so they survive
DATA_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))

STATIC_DIR = os.path.join(APP_DIR, "static")
RESULTS_DIR = os.path.join(DATA_DIR, "results")

# How many rows are sent to the browser (the Excel file always holds everything)
UI_ROW_LIMIT = 3000


# ----------------------------------------------------------------------------
# State of the current job
# ----------------------------------------------------------------------------

class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.running = False
        self.log: list[str] = []
        self.phase = ""
        self.done = 0
        self.total = 0
        self.summary: dict | None = None
        self.error: str | None = None
        self.xlsx: str | None = None
        self.results: dict = {"hits": [], "broken": [], "pages": [], "orphans": []}
        self.stop_event = threading.Event()
        self.auditor: core.SiteAuditor | None = None

    def add_log(self, msg: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.log.append(f"[{stamp}] {msg}")
            if len(self.log) > 5000:
                del self.log[:1000]

    def set_progress(self, phase: str, done: int, total: int):
        with self.lock:
            self.phase, self.done, self.total = phase, done, total


job = Job()


def run_audit(opts: core.Options):
    """Background thread: runs the audit and stores results on the job."""
    try:
        auditor = core.SiteAuditor(
            opts,
            on_log=job.add_log,
            on_progress=job.set_progress,
            stop_event=job.stop_event,
        )
        job.auditor = auditor
        summary = auditor.run()
        # The Excel file is NOT built automatically - only when "Download" is clicked
        job.add_log("Results are ready.")

        with job.lock:
            job.summary = summary
            job.results = {
                "hits": [
                    {
                        "page": h.page, "absolute": h.absolute, "href": h.href,
                        "text": h.text, "tag": h.tag, "context": h.context,
                        "where": h.where, "visible": h.visible,
                        "no_internal": h.no_internal,
                        "kind": h.kind, "kind_text": core.MATCH_KINDS[h.kind],
                        "source_canonical": h.source_canonical,
                        "nofollow": h.nofollow,
                        "target_index_status": h.target_index_status,
                        "target_index_reason": h.target_index_reason,
                        "source_index_status": h.source_index_status,
                        "source_index_reason": h.source_index_reason,
                        "status": h.status if isinstance(h.status, (int, str)) else None,
                        "status_text": core.describe_status(h.status) if h.status is not None else "",
                    }
                    for h in auditor.search_hits[:UI_ROW_LIMIT]
                ],
                "broken": [
                    {
                        "page": b["page"], "link": b["link"], "status": b["status"],
                        "reason": b["reason"], "text": b["text"],
                        "tag": b["tag"], "scope": b["scope"], "count": b.get("count", 1),
                        "where": b["where"], "visible": b["visible"],
                    }
                    for b in auditor.broken[:UI_ROW_LIMIT]
                ],
                "pages": [
                    {
                        "url": p.url, "status": p.status, "title": p.title,
                        "links_out": p.links_count, "inbound": p.inbound, "error": p.error,
                        "index_status": p.index_status, "index_reason": p.index_reason,
                        "indexable": p.indexable,
                    }
                    for p in sorted(
                        (pg for pg in auditor.pages.values()
                         if not opts.only_non_indexable or not pg.indexable),
                        key=lambda x: x.url,
                    )[:UI_ROW_LIMIT]
                ],
                "orphans": auditor.orphans[:UI_ROW_LIMIT],
            }
    except Exception:
        tb = traceback.format_exc()
        job.add_log("ERROR:\n" + tb)
        with job.lock:
            job.error = tb.strip().splitlines()[-1]
    finally:
        with job.lock:
            job.running = False


_export_lock = threading.Lock()


def build_xlsx() -> str | None:
    """
    Builds the Excel file on demand (the "Download" button was clicked).
    Repeated clicks return the file that already exists instead of rebuilding it.
    """
    with _export_lock:
        with job.lock:
            if job.xlsx and os.path.exists(job.xlsx):
                return job.xlsx
            auditor, ready = job.auditor, job.summary is not None
        if not auditor or not ready:
            return None

        os.makedirs(RESULTS_DIR, exist_ok=True)
        host = urlparse(auditor.root).netloc.replace(":", "_")
        path = os.path.join(RESULTS_DIR, f"{host}_{datetime.now():%Y-%m-%d_%H%M%S}.xlsx")
        job.add_log("Building the Excel file ...")
        core.export_xlsx(auditor, path)
        job.add_log(f"File saved: {path}")
        with job.lock:
            job.xlsx = path
        return path


# ----------------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # keep the console clean

    # -- helpers ------------------------------------------------------------

    def send_bytes(self, data: bytes, ctype: str, status: int = 200, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict, status: int = 200):
        self.send_bytes(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def send_text(self, text: str, status: int = 200):
        self.send_bytes(text.encode("utf-8"), "text/plain; charset=utf-8", status)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def serve_static(self, rel_path: str) -> bool:
        """Serves a file from static/. Returns False if there is no such file."""
        rel_path = unquote(rel_path).lstrip("/")
        full = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
        # never let a request escape the static directory
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            return False
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith(("text/", "application/javascript")):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self.send_bytes(f.read(), ctype)
        return True

    # -- routes -------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path

        if route in ("/", "/index.html"):
            if not self.serve_static("index.html"):
                self.send_text("static/index.html not found", 500)
            return

        if route.startswith("/static/"):
            if not self.serve_static(route[len("/static/"):]):
                self.send_text("Not found", 404)
            return

        if route == "/api/status":
            since = int((parse_qs(parsed.query).get("since") or ["0"])[0])
            with job.lock:
                payload = {
                    "version": VERSION,
                    "running": job.running,
                    "phase": job.phase,
                    "done": job.done,
                    "total": job.total,
                    "log": job.log[since:],
                    "log_len": len(job.log),
                    "summary": job.summary,
                    "error": job.error,
                    # results are sent only once finished, so we do not push
                    # megabytes of JSON on every poll
                    "results": job.results if (job.summary and not job.running) else None,
                }
            self.send_json(payload)
            return

        if route == "/api/download":
            try:
                path = build_xlsx()
            except Exception as e:
                self.send_text(f"Could not build the file: {e}", 500)
                return
            if not path:
                self.send_text("Run a scan first", 404)
                return
            with open(path, "rb") as f:
                data = f.read()
            self.send_bytes(
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                extra={"Content-Disposition": f'attachment; filename="{os.path.basename(path)}"'},
            )
            return

        if route == "/api/open-folder":
            os.makedirs(RESULTS_DIR, exist_ok=True)
            try:
                os.startfile(RESULTS_DIR)  # Windows
            except Exception:
                pass
            self.send_json({"ok": True, "path": RESULTS_DIR})
            return

        self.send_text("Not found", 404)

    def do_POST(self):
        route = urlparse(self.path).path

        if route == "/api/start":
            with job.lock:
                if job.running:
                    self.send_json({"ok": False, "error": "A scan is already running"}, 409)
                    return
            data = self.read_json()
            domain = (data.get("domain") or "").strip()
            if not domain:
                self.send_json({"ok": False, "error": "Enter a domain"}, 400)
                return

            mode = data.get("mode") or "search"
            query = (data.get("query") or "").strip()
            if mode in ("search", "full") and not query:
                self.send_json({"ok": False, "error": "Enter what to search for"}, 400)
                return

            def num(key, default=None):
                """Empty field -> default. Zero stays 0 (depth 0 is meaningful)."""
                v = data.get(key)
                if v is None or (isinstance(v, str) and not v.strip()):
                    return default
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return default

            opts = core.Options(
                domain=domain,
                mode=mode,
                query=query,
                match=data.get("match") or "contains",
                limit=num("limit") or None,   # 0 = no limit
                max_depth=num("max_depth"),
                workers=max(1, min(32, num("workers", 10) or 10)),
                delay=float(data.get("delay") or 0),
                include_subdomains=bool(data.get("include_subdomains")),
                use_sitemap=data.get("use_sitemap", True) is not False,
                use_crawl=data.get("use_crawl", True) is not False,
                check_external=bool(data.get("check_external")),
                check_assets=bool(data.get("check_assets")),
                find_orphans=bool(data.get("find_orphans")),
                only_non_indexable=bool(data.get("only_non_indexable")),
                respect_robots=bool(data.get("respect_robots")),
                search_raw_html=data.get("search_raw_html", True) is not False,
                exclude=[x.strip() for x in (data.get("exclude") or "").split(",") if x.strip()],
            )

            job.reset()
            with job.lock:
                job.running = True
            threading.Thread(target=run_audit, args=(opts,), daemon=True).start()
            self.send_json({"ok": True})
            return

        if route == "/api/stop":
            job.stop_event.set()
            job.add_log("Stop requested - finishing the current batch ...")
            self.send_json({"ok": True})
            return

        self.send_text("Not found", 404)


class Server(ThreadingHTTPServer):
    """
    HTTPServer enables SO_REUSEADDR by default. On Windows that lets a second
    process bind a port another process is already listening on: the new copy
    looks like it started fine, but every request still reaches the first one -
    so an updated build appears to run while serving the old code. Turning the
    option off makes binding fail honestly, so the port search below works.
    """
    allow_reuse_address = False
    daemon_threads = True


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # if 8765 is taken (a second copy is already running), take the next one
    server, port = None, PORT
    for candidate in range(PORT, PORT + 20):
        try:
            server = Server((HOST, candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        print(f"Could not bind any port in range {PORT}-{PORT + 19}.")
        return

    if port != PORT:
        print(f"  NOTE: port {PORT} is taken by another copy - using {port} instead")

    url = f"http://{HOST}:{port}"
    print("=" * 60)
    print(f"  Site Link Finder - version {VERSION}")
    print(f"  Interface: {url}")
    print(f"  Results:   {RESULTS_DIR}")
    print("  Stop: press Ctrl+C in this window")
    print("=" * 60)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
