"""Desktop notifications + do-not-disturb (Stage B).

@use levels: snapshot/set_dnd are medium; send_test is low use.
Preoptimized: try_run for gsettings/notify-send; ternary DND merge.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ..preopt import try_run
from ..util import executable
from .base import command_error, dispatch_command

SettingsGet = Callable[[], dict[str, Any]]
SettingsUpdate = Callable[[dict[str, Any]], dict[str, Any]]

_CINNAMON_SCHEMA = "org.cinnamon.desktop.notifications"
_CINNAMON_KEY = "display-notifications"


def sanitize_notify_text(value: Any, limit: int) -> str:
    # @use: low use — purpose: strip control chars from notify-send title/body (one loop)
    text = str(value or "")
    cleaned = "".join(ch for ch in text if ch >= " " and ch != "\x7f")
    return cleaned[:limit]


class NotificationsAdapter:
    """Test notify-send + DND toggle with Cinnamon/local backends."""

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
        # @use: medium use — purpose: Desktop DND chip + can_send affordance
        now = time.monotonic()
        cached = self._cached_snapshot
        if cached is not None and now - self._cached_at < self.cache_ttl:
            return cached.copy()
        local_dnd = self._local_dnd()
        host = self._cinnamon_dnd()
        # Ternary merge: host DND ORs with local; backend label follows host presence.
        snapshot = {
            "available": True,
            "can_send": bool(self.notify_send),
            "dnd": local_dnd if host is None else (local_dnd or host),
            "dnd_backend": "local" if host is None else "cinnamon",
        }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _cinnamon_dnd(self) -> bool | None:
        # @use: medium use — purpose: read Cinnamon display-notifications inverted DND
        if not self.gsettings:
            return None
        run = try_run(
            [self.gsettings, "get", _CINNAMON_SCHEMA, _CINNAMON_KEY],
            timeout=3,
        )
        if not run.ok:
            return None
        # display-notifications false ⇒ DND on
        return run.stdout.strip().lower() in {"false", "'false'"}

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: send_test/set_dnd via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "send_test": self._send_test,
            "set_dnd": self._set_dnd,
        }

    def _local_dnd(self) -> bool:
        return bool(self.settings_get().get("behavior", {}).get("do_not_disturb", False))

    def _set_dnd(self, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: persist DND + best-effort Cinnamon gsettings
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            return command_error("invalid_argument", "enabled must be a boolean")
        self.settings_update({"behavior": {"do_not_disturb": enabled}})
        # Invert: DND on ⇒ hide desktop notifications (best-effort; ignore failures).
        self.gsettings and try_run(
            [
                self.gsettings,
                "set",
                _CINNAMON_SCHEMA,
                _CINNAMON_KEY,
                "false" if enabled else "true",
            ],
            timeout=3,
        )
        self._cached_snapshot = None
        return {
            "ok": True,
            "dnd": enabled,
            "dnd_backend": "cinnamon" if self.gsettings else "local",
        }

    def _send_test(self, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: notify-send test bubble (skipped when DND)
        if self._local_dnd() or self.snapshot().get("dnd"):
            return {"ok": True, "skipped": True, "reason": "do_not_disturb"}
        if not self.notify_send:
            return command_error("unavailable", "notify-send is not installed")
        title = sanitize_notify_text(payload.get("title", "LMDesktopPlus"), 80) or "LMDesktopPlus"
        body = (
            sanitize_notify_text(payload.get("body", "Test notification"), 200)
            or "Test notification"
        )
        run = try_run(
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
        if not run.launched:
            return command_error("internal_error", run.error)
        return (
            {"ok": True}
            if run.ok
            else command_error(
                "internal_error",
                run.stderr.strip() or "notify-send failed",
            )
        )
