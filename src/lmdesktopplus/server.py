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
from .adapters.audio import AudioAdapter
from .adapters.base import classify_exception, command_error
from .adapters.bluetooth import BluetoothAdapter
from .adapters.capture import CaptureAdapter
from .adapters.clipboard import ClipboardAdapter
from .adapters.display import DisplayAdapter
from .adapters.notifications import NotificationsAdapter
from .adapters.processes import ProcessAdapter
from .adapters.session import SessionAdapter
from .adapters.storage import RemovableStorageAdapter
from .adapters.updates import UpdatesAdapter
from .adapters.keybinds import ChordAdapter
from .adapters.vault import VaultAdapter
from .adapters.vpn import VpnAdapter
from .adapters.wallpaper import WallpaperAdapter
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
        self.adapters.register(AudioAdapter())
        self.adapters.register(DisplayAdapter())
        self.adapters.register(SessionAdapter())
        self.adapters.register(BluetoothAdapter())
        self.adapters.register(
            NotificationsAdapter(
                settings_get=self.settings.get,
                settings_update=self.settings.update,
            )
        )
        self.adapters.register(UpdatesAdapter())
        self.adapters.register(ClipboardAdapter())
        self.adapters.register(CaptureAdapter())
        self.adapters.register(VpnAdapter())
        self.adapters.register(RemovableStorageAdapter())
        self.adapters.register(ProcessAdapter())
        self.adapters.register(ChordAdapter())
        self.adapters.register(VaultAdapter())
        self.wallpaper = WallpaperAdapter()
        self.adapters.register(self.wallpaper)
        self.assets = AssetCatalog(self.wallpaper.wallpaper_map)
        self.system = SystemSampler()
        self.actions = ActionRunner(self.settings.get)
        self.started = time.time()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.RLock()
        self._key_locks: dict[str, threading.Lock] = {}
        self._key_locks_guard = threading.Lock()
        # Prime CPU/net deltas so the first visible sample is useful.
        self.system.sample()

    def _lock_for(self, key: str) -> threading.Lock:
        with self._key_locks_guard:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[key] = lock
            return lock

    def cached(self, key: str, seconds: float, loader):
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry and now - entry[0] < seconds:
                return entry[1]
        # Load outside the shared cache lock so slow host tools do not block
        # unrelated keys; per-key lock collapses stampedes.
        with self._lock_for(key):
            now = time.monotonic()
            with self._cache_lock:
                entry = self._cache.get(key)
                if entry and now - entry[0] < seconds:
                    return entry[1]
            value = loader()
            with self._cache_lock:
                self._cache[key] = (time.monotonic(), value)
            return value

    def adapters_snapshot(self) -> dict[str, dict[str, Any]]:
        return self.adapters.as_dict()

    def snapshot_core(self) -> dict[str, Any]:
        return {
            "version": __version__,
            "server_uptime_seconds": int(time.time() - self.started),
            "identity": self.system.identity(),
            "settings": self.settings.get(),
            "accents": ACCENTS,
            "agents": self.agents.list(),
            "capabilities": self.actions.capabilities(),
        }

    def snapshot_metrics(self) -> dict[str, Any]:
        return {"metrics": self.system.sample()}

    def snapshot_adapters(self) -> dict[str, Any]:
        return {"adapters": self.adapters_snapshot()}

    def snapshot_network(self) -> dict[str, Any]:
        return {"network": self.cached("network-current", 5.0, network.current)}

    def snapshot_media(self) -> dict[str, Any]:
        return {"media": self.cached("media", 1.5, media.status)}

    def snapshot_assets(self) -> dict[str, Any]:
        return {
            "assets": self.assets.as_dict(),
            "assets_revision": self.assets.revision(),
        }

    def snapshot(self) -> dict[str, Any]:
        # Aggregate kept for one release; domain endpoints prefer independent refresh.
        out = {}
        out.update(self.snapshot_core())
        out.update(self.snapshot_metrics())
        out.update(self.snapshot_adapters())
        out.update(self.snapshot_assets())
        out.update(self.snapshot_network())
        out.update(self.snapshot_media())
        return out


class ControlServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: ApplicationState):
        self.state = state
        self.token = secrets.token_urlsafe(32)
        self.origin = f"http://{address[0]}:{address[1]}" if address[1] else None
        super().__init__(address, RequestHandler)
        host, port = self.server_address[:2]
        self.origin = f"http://{host}:{port}"


class RequestHandler(BaseHTTPRequestHandler):
    server: ControlServer

    # Exact-path GET handlers: (requires_auth, handler_name)
    GET_ROUTES: dict[str, tuple[bool, str]] = {
        "/api/v1/network/scan": (True, "_get_network_scan"),
    }
    # Longest-prefix-first GET handlers: (prefix, requires_auth, handler_name)
    GET_PREFIX_ROUTES: tuple[tuple[str, bool, str], ...] = (
        ("/api/v1/state", True, "_get_state"),
        ("/wallpaper-thumbs/", False, "_serve_wallpaper_thumbnail"),
    )
    # Exact-path POST handlers (auth + JSON body already gated in do_POST)
    POST_ROUTES: dict[str, str] = {
        "/api/v1/settings": "_post_settings",
        "/api/v1/action": "_post_action",
        "/api/v1/agents": "_post_agents",
        "/api/v1/agents/launch": "_post_agents_launch",
        "/api/v1/media": "_post_media",
        "/api/v1/network/connect": "_post_network_connect",
        "/api/v1/network/disconnect": "_post_network_disconnect",
    }
    POST_PREFIX_ROUTES: tuple[tuple[str, str], ...] = (
        ("/api/v1/adapter/", "_post_adapter"),
    )

    def log_message(self, fmt: str, *args: Any) -> None:
        # Avoid leaking network passwords or noisy polling into stdout.
        if self.path.startswith("/api/v1/state"):
            return
        super().log_message(fmt, *args)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        exact = self.GET_ROUTES.get(path)
        if exact is not None:
            needs_auth, name = exact
            if needs_auth and not self._authorized():
                return
            getattr(self, name)(path)
            return
        for prefix, needs_auth, name in self.GET_PREFIX_ROUTES:
            base = prefix.rstrip("/")
            if path == base or path.startswith(base + "/") or (
                prefix.endswith("/") and path.startswith(prefix)
            ):
                if needs_auth and not self._authorized():
                    return
                getattr(self, name)(path)
                return
        self._serve_static(path)

    def do_POST(self) -> None:
        if not self._authorized():
            return
        body = self._read_json()
        if body is None:
            return
        path = urlparse(self.path).path
        exact = self.POST_ROUTES.get(path)
        if exact is not None:
            getattr(self, exact)(body)
            return
        for prefix, name in self.POST_PREFIX_ROUTES:
            if path.startswith(prefix):
                getattr(self, name)(path, body)
                return
        self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})

    def _get_state(self, path: str) -> None:
        domain = path.removeprefix("/api/v1/state").strip("/")
        state = self.server.state
        if domain in {"", "full"}:
            self._json(HTTPStatus.OK, state.snapshot())
            return
        loaders = {
            "core": state.snapshot_core,
            "metrics": state.snapshot_metrics,
            "adapters": state.snapshot_adapters,
            "network": state.snapshot_network,
            "media": state.snapshot_media,
            "assets": state.snapshot_assets,
        }
        loader = loaders.get(domain)
        if loader is None:
            self._json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": f"unknown state domain: {domain}"},
            )
            return
        self._json(HTTPStatus.OK, loader())

    def _get_network_scan(self, _path: str) -> None:
        self._json(HTTPStatus.OK, network.scan_wifi(rescan=True))

    def _post_settings(self, body: dict[str, Any]) -> None:
        patch = body.get("patch")
        if not isinstance(patch, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "patch must be an object"})
            return
        settings = self.server.state.settings.update(patch)
        applied = theme.apply(settings) if body.get("apply", True) else {"ok": True, "results": []}
        self._json(HTTPStatus.OK, {"ok": True, "settings": settings, "applied": applied})

    def _post_action(self, body: dict[str, Any]) -> None:
        result = self.server.state.actions.run(
            str(body.get("action", "")),
            str(body.get("target", "")) or None,
        )
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _post_agents(self, body: dict[str, Any]) -> None:
        """Roster CRUD: body.op ∈ create|update|delete (vapor: forge|retune|melt)."""
        from .agents import dispatch_peer_op

        # Prefer explicit `op`; accept vapor aliases via dispatch_peer_op.
        op = str(body.get("op") or body.get("action") or "").strip()
        # Payload may be nested or flat beside `op`.
        payload = body.get("payload")
        if not isinstance(payload, dict):
            payload = {key: value for key, value in body.items() if key not in {"op", "action", "payload"}}
        result = dispatch_peer_op(self.server.state.agents, op, payload)
        # Refresh cached aggregate state so the next poll sees roster changes.
        with self.server.state._cache_lock:
            self.server.state._cache.pop("core", None)
            self.server.state._cache.pop("full", None)
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _post_agents_launch(self, body: dict[str, Any]) -> None:
        # Spawn keeps its own path so a stray CRUD click cannot launch.
        result = self.server.state.agents.spawn_peer(str(body.get("name", "")))
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _post_media(self, body: dict[str, Any]) -> None:
        result = media.control(str(body.get("action", "")))
        with self.server.state._cache_lock:
            self.server.state._cache.pop("media", None)
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _post_network_connect(self, body: dict[str, Any]) -> None:
        result = network.connect_wifi(
            str(body.get("ssid", "")),
            str(body.get("password", "")) or None,
        )
        with self.server.state._cache_lock:
            self.server.state._cache.pop("network-current", None)
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _post_network_disconnect(self, body: dict[str, Any]) -> None:
        result = network.disconnect(str(body.get("device", "")))
        with self.server.state._cache_lock:
            self.server.state._cache.pop("network-current", None)
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _post_adapter(self, path: str, body: dict[str, Any]) -> None:
        adapter_id = path.removeprefix("/api/v1/adapter/")
        name = body.get("name")
        payload = body.get("payload", {})
        if not adapter_id or "/" in adapter_id:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown adapter"})
            return
        if not isinstance(name, str) or not name:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "name must be a non-empty string"},
            )
            return
        if not isinstance(payload, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "payload must be an object"})
            return
        state = self.server.state
        try:
            adapter = state.adapters.get(adapter_id)
        except KeyError:
            self._json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": f"unknown adapter: {adapter_id}"},
            )
            return
        try:
            result = adapter.command(name, payload)
        except Exception as exc:  # noqa: BLE001 — boundary for API JSON stability
            code, _message = classify_exception(exc)
            # Log details locally; never send raw exception text to the UI by default.
            self.log_error(
                "Adapter command failed adapter=%s name=%s err=%s",
                adapter_id,
                name,
                exc,
            )
            result = command_error(
                code if code != "internal_error" else "internal_error",
                "Adapter command failed",
            )
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _authorized(self) -> bool:
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "loopback clients only"})
            return False
        if self.headers.get("X-LMDP-Token") != self.server.token:
            self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid UI token"})
            return False
        if not self._origin_allowed():
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin not allowed"})
            return False
        return True

    def _origin_allowed(self) -> bool:
        """Defense in depth on top of loopback + token checks.

        Only the exact bound server origin (and matching Host forms) are
        accepted. Foreign localhost ports, Origin: null, and cross-site
        fetches are rejected.
        """
        expected = self.server.origin
        if not expected:
            return False
        expected_host = expected.removeprefix("http://").removeprefix("https://")
        port = self.server.server_address[1]
        allowed_hosts = {
            expected_host,
            f"127.0.0.1:{port}",
            f"localhost:{port}",
            "[::1]:" + str(port),
        }
        host = self.headers.get("Host", "")
        if host and host not in allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and origin != expected:
            return False
        site = self.headers.get("Sec-Fetch-Site", "")
        if site == "cross-site":
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
        allowed_static = {
            "index.html",
            "app.js",
            "bindings.js",
            "style.css",
            "digitalvapor.css",
            "digitalvapor.js",
        }
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

    def _serve_wallpaper_thumbnail(self, url_path: str) -> None:
        filename = url_path.removeprefix("/wallpaper-thumbs/")
        if not filename.endswith(".png") or "/" in filename:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        wallpaper_id = filename.removesuffix(".png")
        thumbnail = self.server.state.wallpaper.thumbnail_path(wallpaper_id)
        if thumbnail is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            data = thumbnail.read_bytes()
        except (FileNotFoundError, IsADirectoryError, OSError):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
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
