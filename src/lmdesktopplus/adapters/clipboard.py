"""Session clipboard peek/copy with RAM-only history (Stage B).

@use levels: snapshot/peek are medium; copy/clear are low use.
Never writes clipboard contents to disk.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections import deque
from typing import Any

from ..util import executable, run_capture
from .base import dispatch_command

MAX_COPY_BYTES = 64 * 1024
PREVIEW_LIMIT = 500
HISTORY_LIMIT = 20


class ClipboardAdapter:
    """Wayland wl-clipboard or X11 xclip — session-matched fail-soft."""

    id = "clipboard"

    def __init__(
        self,
        cache_ttl: float = 2.0,
        session_type: str | None = None,
        wl_paste: str | None = None,
        wl_copy: str | None = None,
        xclip: str | None = None,
    ) -> None:
        self.session_type = (session_type or os.environ.get("XDG_SESSION_TYPE") or "").lower()
        self.wl_paste = executable("wl-paste") if wl_paste is None else (wl_paste or None)
        self.wl_copy = executable("wl-copy") if wl_copy is None else (wl_copy or None)
        self.xclip = executable("xclip") if xclip is None else (xclip or None)
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None
        self._history: deque[str] = deque(maxlen=HISTORY_LIMIT)

    def _backend(self) -> str | None:
        # @use: medium use — purpose: session-routed clipboard tool selection
        order_by_session = {
            "wayland": ("wl-clipboard", "xclip"),
            "x11": ("xclip", "wl-clipboard"),
        }
        order = order_by_session.get(self.session_type, ("wl-clipboard", "xclip"))
        present = {
            "wl-clipboard": bool(self.wl_paste and self.wl_copy),
            "xclip": bool(self.xclip),
        }
        for name in order:
            if present.get(name):
                return name
        return None

    def available(self) -> bool:
        return self._backend() is not None

    def snapshot(self) -> dict[str, Any]:
        # @use: medium use — purpose: Desktop clipboard preview poll
        backend = self._backend()
        if not backend:
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        try:
            text = self._peek_raw(backend)
            preview = text[:PREVIEW_LIMIT]
            snapshot = {
                "available": True,
                "backend": backend,
                "preview": preview,
                "truncated": len(text) > PREVIEW_LIMIT,
                "length": len(text),
            }
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            snapshot = {
                "available": False,
                "backend": backend,
                "last_error": str(exc),
            }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: peek/copy/clear/history via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "history": self._cmd_history,
            "peek": self._cmd_peek,
            "clear": self._cmd_clear,
            "copy": self._cmd_copy,
        }

    def _cmd_history(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "items": list(self._history)}

    def _cmd_peek(self, _payload: dict[str, Any]) -> dict[str, Any]:
        self._cached_snapshot = None
        snap = self.snapshot()
        if not snap.get("available"):
            return {"ok": False, "error": snap.get("last_error") or "clipboard unavailable"}
        return {"ok": True, **snap}

    def _cmd_clear(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return self._copy_text("")

    def _cmd_copy(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = payload.get("text")
        if not isinstance(text, str):
            return {"ok": False, "error": "text must be a string"}
        if len(text.encode("utf-8", errors="replace")) > MAX_COPY_BYTES:
            return {"ok": False, "error": f"text exceeds {MAX_COPY_BYTES} bytes"}
        return self._copy_text(text)

    def _peek_raw(self, backend: str) -> str:
        # @use: medium use — purpose: read clipboard text for preview (RAM only)
        peekers = {
            "wl-clipboard": lambda: run_capture([self.wl_paste, "-n"], timeout=3),
            "xclip": lambda: run_capture(
                [self.xclip, "-selection", "clipboard", "-o"],
                timeout=3,
            ),
        }
        result = peekers[backend]()
        if result.returncode != 0:
            # Empty clipboard is common; treat as empty text when tool exists
            err = (result.stderr or "").lower()
            if "not available" in err or "no target" in err or result.returncode == 1:
                return ""
            raise RuntimeError(result.stderr.strip() or "clipboard peek failed")
        return result.stdout

    def _copy_text(self, text: str) -> dict[str, Any]:
        # @use: low use — purpose: write clipboard + optional RAM history entry
        backend = self._backend()
        if not backend:
            return {"ok": False, "error": "no clipboard tool for this session"}
        writers = {
            "wl-clipboard": lambda: run_capture([self.wl_copy], timeout=3, input_text=text),
            "xclip": lambda: run_capture(
                [self.xclip, "-selection", "clipboard"],
                timeout=3,
                input_text=text,
            ),
        }
        try:
            result = writers[backend]()
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "clipboard copy failed"}
        preview = text[:PREVIEW_LIMIT]
        if text:
            self._history.appendleft(preview)
        self._cached_snapshot = None
        return {"ok": True, "length": len(text), "preview": preview}
