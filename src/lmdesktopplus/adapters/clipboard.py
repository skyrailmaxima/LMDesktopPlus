from __future__ import annotations

import os
import subprocess
import time
from collections import deque
from typing import Any

from ..util import executable, run_capture

MAX_COPY_BYTES = 64 * 1024
PREVIEW_LIMIT = 500
HISTORY_LIMIT = 20


class ClipboardAdapter:
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
        if self.session_type == "wayland":
            if self.wl_paste and self.wl_copy:
                return "wl-clipboard"
            if self.xclip:
                return "xclip"
            return None
        if self.session_type == "x11":
            if self.xclip:
                return "xclip"
            if self.wl_paste and self.wl_copy:
                return "wl-clipboard"
            return None
        if self.wl_paste and self.wl_copy:
            return "wl-clipboard"
        if self.xclip:
            return "xclip"
        return None

    def available(self) -> bool:
        return self._backend() is not None

    def snapshot(self) -> dict[str, Any]:
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
        if name not in {"peek", "copy", "clear", "history"}:
            return {"ok": False, "error": f"unknown clipboard command: {name}"}
        if name == "history":
            return {"ok": True, "items": list(self._history)}
        if name == "peek":
            self._cached_snapshot = None
            snap = self.snapshot()
            if not snap.get("available"):
                return {"ok": False, "error": snap.get("last_error") or "clipboard unavailable"}
            return {"ok": True, **snap}
        if name == "clear":
            return self._copy_text("")
        text = payload.get("text")
        if not isinstance(text, str):
            return {"ok": False, "error": "text must be a string"}
        if len(text.encode("utf-8", errors="replace")) > MAX_COPY_BYTES:
            return {"ok": False, "error": f"text exceeds {MAX_COPY_BYTES} bytes"}
        return self._copy_text(text)

    def _peek_raw(self, backend: str) -> str:
        if backend == "wl-clipboard":
            result = run_capture([self.wl_paste, "-n"], timeout=3)
        else:
            result = run_capture(
                [self.xclip, "-selection", "clipboard", "-o"],
                timeout=3,
            )
        if result.returncode != 0:
            # Empty clipboard is common; treat as empty text when tool exists
            err = (result.stderr or "").lower()
            if "not available" in err or "no target" in err or result.returncode == 1:
                return ""
            raise RuntimeError(result.stderr.strip() or "clipboard peek failed")
        return result.stdout

    def _copy_text(self, text: str) -> dict[str, Any]:
        backend = self._backend()
        if not backend:
            return {"ok": False, "error": "no clipboard tool for this session"}
        try:
            if backend == "wl-clipboard":
                result = run_capture([self.wl_copy], timeout=3, input_text=text)
            else:
                result = run_capture(
                    [self.xclip, "-selection", "clipboard"],
                    timeout=3,
                    input_text=text,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "clipboard copy failed"}
        preview = text[:PREVIEW_LIMIT]
        if text:
            self._history.appendleft(preview)
        self._cached_snapshot = None
        return {"ok": True, "length": len(text), "preview": preview}
