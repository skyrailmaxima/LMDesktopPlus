from __future__ import annotations

from typing import Any

from .util import executable, run_capture


def status() -> dict[str, Any]:
    if not executable("playerctl"):
        return {"available": False, "status": "Stopped", "title": None, "artist": None, "album": None}
    cp = run_capture(["playerctl", "metadata", "--format", "{{status}}\t{{artist}}\t{{title}}\t{{album}}"], timeout=2)
    if cp.returncode != 0 or not cp.stdout.strip():
        return {"available": True, "status": "Stopped", "title": None, "artist": None, "album": None}
    parts = cp.stdout.strip().split("\t", 3)
    parts += [""] * (4 - len(parts))
    return {"available": True, "status": parts[0], "artist": parts[1] or None, "title": parts[2] or None, "album": parts[3] or None}


def control(action: str) -> dict[str, Any]:
    allowed = {"play-pause", "play", "pause", "next", "previous", "stop"}
    if action not in allowed:
        return {"ok": False, "error": "unsupported media action"}
    if not executable("playerctl"):
        return {"ok": False, "error": "playerctl is not installed"}
    cp = run_capture(["playerctl", action], timeout=3)
    return {"ok": cp.returncode == 0, "error": cp.stderr.strip() if cp.returncode else None, "media": status()}
