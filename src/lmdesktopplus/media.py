"""playerctl media status/control — preopt try_run on host edges.

@use levels: status is high (core poll); control is medium.
"""

from __future__ import annotations

from typing import Any

from .fncache import UseLevel, register_fn
from .preopt import try_run
from .util import executable

_ALLOWED_ACTIONS = frozenset({"play-pause", "play", "pause", "next", "previous", "stop"})


@register_fn(
    "media.status",
    UseLevel.HIGH,
    "playerctl metadata probe without raising into poll",
)
def status() -> dict[str, Any]:
    # @use: high use — purpose: Desktop media strip; timeout → Stopped soft
    stopped = {
        "available": True,
        "status": "Stopped",
        "title": None,
        "artist": None,
        "album": None,
    }
    if not executable("playerctl"):
        return {
            "available": False,
            "status": "Stopped",
            "title": None,
            "artist": None,
            "album": None,
        }
    run = try_run(
        [
            "playerctl",
            "metadata",
            "--format",
            "{{status}}\t{{artist}}\t{{title}}\t{{album}}",
        ],
        timeout=2,
    )
    if not run.ok or not run.stdout.strip():
        return stopped
    parts = run.stdout.strip().split("\t", 3)
    parts += [""] * (4 - len(parts))
    return {
        "available": True,
        "status": parts[0],
        "artist": parts[1] or None,
        "title": parts[2] or None,
        "album": parts[3] or None,
    }


@register_fn(
    "media.control",
    UseLevel.MEDIUM,
    "Allowlisted playerctl action via try_run",
)
def control(action: str) -> dict[str, Any]:
    # @use: medium use — purpose: media transport buttons
    if action not in _ALLOWED_ACTIONS:
        return {"ok": False, "error": "unsupported media action"}
    if not executable("playerctl"):
        return {"ok": False, "error": "playerctl is not installed"}
    run = try_run(["playerctl", action], timeout=3)
    return {
        "ok": run.ok,
        "error": None if run.ok else (run.error or run.stderr.strip() or "playerctl failed"),
        "media": status(),
    }
