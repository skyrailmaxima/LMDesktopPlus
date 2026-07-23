from __future__ import annotations

import subprocess
import time
from typing import Any, Callable

from ..util import executable, run_capture

SettingsGet = Callable[[], dict[str, Any]]
SettingsUpdate = Callable[[dict[str, Any]], dict[str, Any]]

_CINNAMON_SCHEMA = "org.cinnamon.desktop.notifications"
_CINNAMON_KEY = "display-notifications"


def sanitize_notify_text(value: Any, limit: int) -> str:
    text = str(value or "")
    cleaned = "".join(ch for ch in text if ch >= " " and ch != "\x7f")
    return cleaned[:limit]


class NotificationsAdapter:
    id = "notifications"

    def __init__(
        self,
        settings_get: SettingsGet,
        settings_update: SettingsUpdate,
        cache_ttl: float = 5.0,
        notify_send: str | None = None,
        gsettings: str | None = None,
    ) -> None:
        self.settings_get = settings_get
        self.settings_update = settings_update
        self.cache_ttl = cache_ttl
        self.notify_send = notify_send if notify_send is not None else executable("notify-send")
        self.gsettings = gsettings if gsettings is not None else executable("gsettings")
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return True

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        local_dnd = bool(self.settings_get().get("behavior", {}).get("do_not_disturb", False))
        dnd = local_dnd
        dnd_backend = "local"
        if self.gsettings:
            try:
                result = run_capture(
                    [self.gsettings, "get", _CINNAMON_SCHEMA, _CINNAMON_KEY],
                    timeout=3,
                )
                if result.returncode == 0:
                    # display-notifications false ⇒ DND on
                    host_dnd = result.stdout.strip().lower() in {"false", "'false'"}
                    dnd = local_dnd or host_dnd
                    dnd_backend = "cinnamon"
            except (OSError, subprocess.TimeoutExpired):
                pass
        snapshot = {
            "available": True,
            "can_send": bool(self.notify_send),
            "dnd": dnd,
            "dnd_backend": dnd_backend,
        }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name not in {"send_test", "set_dnd"}:
            return {"ok": False, "error": f"unknown notifications command: {name}"}
        if name == "set_dnd":
            return self._set_dnd(payload)
        return self._send_test(payload)

    def _local_dnd(self) -> bool:
        return bool(self.settings_get().get("behavior", {}).get("do_not_disturb", False))

    def _set_dnd(self, payload: dict[str, Any]) -> dict[str, Any]:
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            return {"ok": False, "error": "enabled must be a boolean"}
        self.settings_update({"behavior": {"do_not_disturb": enabled}})
        if self.gsettings:
            # Invert: DND on ⇒ hide desktop notifications
            display = "false" if enabled else "true"
            try:
                run_capture(
                    [self.gsettings, "set", _CINNAMON_SCHEMA, _CINNAMON_KEY, display],
                    timeout=3,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        self._cached_snapshot = None
        return {"ok": True, "dnd": enabled, "dnd_backend": "cinnamon" if self.gsettings else "local"}

    def _send_test(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._local_dnd() or self.snapshot().get("dnd"):
            return {"ok": True, "skipped": True, "reason": "do_not_disturb"}
        if not self.notify_send:
            return {"ok": False, "error": "notify-send is not installed"}
        title = sanitize_notify_text(payload.get("title", "LMDesktopPlus"), 80) or "LMDesktopPlus"
        body = sanitize_notify_text(payload.get("body", "Test notification"), 200) or "Test notification"
        try:
            result = run_capture(
                [
                    self.notify_send,
                    "-a",
                    "LMDesktopPlus",
                    "-u",
                    "normal",
                    "--",
                    title,
                    body,
                ],
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "notify-send failed"}
        return {"ok": True}
