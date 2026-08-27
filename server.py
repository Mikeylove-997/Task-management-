from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .commands import CommandProcessor
from .config import database_path
from .db import TaskStore

STATIC = Path(__file__).parent / "static"


class MikeOSServer(ThreadingHTTPServer):
    def __init__(self, address, handler, store: TaskStore):
        super().__init__(address, handler)
        self.store = store
        self.commands = CommandProcessor(store)


class Handler(BaseHTTPRequestHandler):
    server: MikeOSServer

    def log_message(self, format: str, *args) -> None:
        return

    def _json(self, data, status=HTTPStatus.OK, headers=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _error(self, exc):
        code = HTTPStatus.NOT_FOUND if isinstance(exc, KeyError) else HTTPStatus.BAD_REQUEST
        self._json({"error": str(exc).strip("'")}, code)

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/tasks":
                params = parse_qs(parsed.query)
                self._json(self.server.store.list(
                    status=params.get("status", [None])[0], query=params.get("q", [None])[0],
                    project=params.get("project", [None])[0]))
            elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/history"):
                task_id = parsed.path.split("/")[3]
                self._json(self.server.store.history(task_id))
            elif parsed.path == "/api/export":
                self._json(self.server.store.export(), headers={"Content-Disposition": "attachment; filename=mike-os-backup.json"})
            else:
                self._static(parsed.path)
        except (ValueError, KeyError) as exc:
            self._error(exc)

    def do_POST(self):
        try:
            if self.path == "/api/tasks":
                self._json(self.server.store.create(self._body()), HTTPStatus.CREATED)
            elif self.path == "/api/command":
                self._json(self.server.commands.execute(self._body().get("text", "")))
            else:
                self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._error(exc)

    def do_PATCH(self):
        try:
            if self.path.startswith("/api/tasks/"):
                self._json(self.server.store.update(self.path.split("/")[3], self._body()))
            else:
                self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._error(exc)

    def _static(self, request_path):
        filename = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (STATIC / filename).resolve()
        if STATIC.resolve() not in candidate.parents and candidate != STATIC.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            candidate = STATIC / "index.html"
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host="127.0.0.1", port=8765, open_browser=True):
    store = TaskStore(database_path())
    server = MikeOSServer((host, port), Handler, store)
    url = f"http://{host}:{port}"
    print(f"Mike OS is running at {url}")
    print(f"Data: {store.path}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMike OS stopped.")
    finally:
        server.server_close()

