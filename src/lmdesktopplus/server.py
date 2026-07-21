from __future__ import annotations

import json
import mimetypes
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .actions import ActionRunner
from .adapters import AdapterRegistry
from .agents import AgentRegistry
from .assets import AssetCatalog
from .config import ACCENTS, SettingsStore
from . import media, network, theme
from .system_info import SystemSampler

MAX_BODY = 1024 * 1024


class ApplicationState:
    def __init__(self) -> None:
        self.settings = SettingsStore()
        self.agents = AgentRegistry()
        self.adapters = AdapterRegistry()
        self.assets = AssetCatalog()
        self.system = SystemSampler()
        self.actions = ActionRunner(self.settings.get)
        self.started = time.time()
        self._cache: dict[str, tuple[float, Any]] = {}
        # Prime CPU/net deltas so the first visible sample is useful.
        self.system.sample()

    def cached(self, key: str, seconds: float, loader):
        now = time.monotonic()
        entry = self._cache.get(key)
        if entry and now - entry[0] < seconds:
            return entry[1]
        value = loader()
        self._cache[key] = (now, value)
        return value

    def adapters_snapshot(self) -> dict[str, dict[str, Any]]:
        return self.adapters.as_dict()

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": __version__,
            "server_uptime_seconds": int(time.time() - self.started),
            "identity": self.system.identity(),
            "metrics": self.system.sample(),
            "settings": self.settings.get(),
            "accents": ACCENTS,
            "agents": self.agents.list(),
            "adapters": self.adapters_snapshot(),
            "assets": self.assets.as_dict(),
            "capabilities": self.actions.capabilities(),
            "network": self.cached("network-current", 5.0, network.current),
            "media": self.cached("media", 1.5, media.status),
        }


class ControlServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: ApplicationState):
        self.state = state
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, RequestHandler)


class RequestHandler(BaseHTTPRequestHandler):
    server: ControlServer

    def log_message(self, fmt: str, *args: Any) -> None:
        # Avoid leaking network passwords or noisy polling into stdout.
        if self.path.startswith("/api/v1/state"):
            return
        super().log_message(fmt, *args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/state":
            if not self._authorized():
                return
            self._json(HTTPStatus.OK, self.server.state.snapshot())
            return
        if parsed.path == "/api/v1/network/scan":
            if not self._authorized():
                return
            self._json(HTTPStatus.OK, network.scan_wifi(rescan=True))
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        if not self._authorized():
            return
        body = self._read_json()
        if body is None:
            return
        path = urlparse(self.path).path
        state = self.server.state
        if path == "/api/v1/settings":
            patch = body.get("patch") if isinstance(body, dict) else None
            if not isinstance(patch, dict):
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "patch must be an object"})
                return
            settings = state.settings.update(patch)
            applied = theme.apply(settings) if body.get("apply", True) else {"ok": True, "results": []}
            self._json(HTTPStatus.OK, {"ok": True, "settings": settings, "applied": applied})
            return
        if path == "/api/v1/action":
            result = state.actions.run(str(body.get("action", "")), str(body.get("target", "")) or None)
            self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)
            return
        if path == "/api/v1/agents/launch":
            result = state.agents.launch(str(body.get("name", "")))
            self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)
            return
        if path == "/api/v1/media":
            result = media.control(str(body.get("action", "")))
            state._cache.pop("media", None)
            self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)
            return
        if path == "/api/v1/network/connect":
            result = network.connect_wifi(str(body.get("ssid", "")), str(body.get("password", "")) or None)
            state._cache.pop("network-current", None)
            self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)
            return
        if path == "/api/v1/network/disconnect":
            result = network.disconnect(str(body.get("device", "")))
            state._cache.pop("network-current", None)
            self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)
            return
        self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})

    def _authorized(self) -> bool:
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "loopback clients only"})
            return False
        if self.headers.get("X-LMDP-Token") != self.server.token:
            self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid UI token"})
            return False
        return True

    def _read_json(self) -> dict[str, Any] | None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if size <= 0 or size > MAX_BODY:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid request size"})
            return None
        try:
            value = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid JSON"})
            return None
        if not isinstance(value, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "request must be an object"})
            return None
        return value

    def _json(self, status: HTTPStatus, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, url_path: str) -> None:
        rel = "index.html" if url_path in {"", "/"} else url_path.lstrip("/")
        parts = Path(rel).parts
        allowed_static = {"index.html", "app.js", "style.css", "digitalvapor.css", "digitalvapor.js"}
        if ".." in parts or not self._allowed_static_path(rel, parts, allowed_static):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        resource = files("lmdesktopplus").joinpath("static", rel)
        try:
            data = resource.read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if rel == "index.html":
            data = data.replace(b"__LMDP_TOKEN__", self.server.token.encode("ascii"))
        ctype = mimetypes.guess_type(rel)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if rel == "index.html" else "max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def _allowed_static_path(rel: str, parts: tuple[str, ...], allowed_static: set[str]) -> bool:
        if rel in allowed_static:
            return True
        if len(parts) == 2 and parts[0] == "icons" and parts[1].endswith(".svg"):
            return True
        return False


def start_server() -> tuple[ControlServer, threading.Thread, str]:
    state = ApplicationState()
    server = ControlServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, name="lmdp-http", daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, thread, url
