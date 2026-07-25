"""App vault — FEATURE_PACKAGES map + allowlisted pkexec apt installs (Tranche 6).

Preoptimized: try_run for dpkg-query / pkexec apt-get; map-first feature rows.
Vapor typology: **vault** (feature catalog), **probe** (scan), **forge_pack**
(install via explicit confirm). Package names never come from the client — only
ids that resolve inside FEATURE_PACKAGES.
"""

from __future__ import annotations

import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import try_run
from ..util import executable
from .base import command_error, dispatch_command

# Canonical vault map — UI and install both consume this hashmap.
FEATURE_PACKAGES: dict[str, dict[str, Any]] = {
    "kitty": {
        "apt": ["kitty"],
        "label": "Kitty terminal",
        "detect": "kitty",
        "cap": "terminal",
    },
    "tmux": {
        "apt": ["tmux"],
        "label": "Persistent sessions",
        "detect": "tmux",
        "cap": "tmux",
    },
    "rofi": {
        "apt": ["rofi"],
        "label": "Application launcher",
        "detect": "rofi",
        "cap": "rofi",
    },
    "waybar": {
        "apt": ["waybar"],
        "label": "Hyprland bar",
        "detect": "waybar",
        "cap": "hyprctl",
    },
    "hyprland": {
        "apt": ["hyprland"],
        "label": "Hyprland session",
        "detect": "Hyprland",
        "cap": None,
    },
    "bluetooth": {
        "apt": ["bluez"],
        "label": "Bluetooth tools",
        "detect": "bluetoothctl",
        "cap": None,
    },
    "starship": {
        "apt": ["starship"],
        "label": "Shell prompt",
        "detect": "starship",
        "cap": None,
    },
    "claude": {
        "apt": [],
        "label": "Claude agent",
        "detect": "claude",
        "cap": "bubblewrap",
    },
    "cursor": {
        "apt": [],
        "label": "Cursor editor",
        "detect": "cursor",
        "cap": "editor",
    },
    "aider": {
        "apt": [],
        "label": "Aider agent",
        "detect": "aider",
        "cap": "bubblewrap",
    },
    "rust": {
        "apt": [],
        "label": "Rust tooling",
        "detect": "rustc",
        "cap": None,
    },
    "minimap": {
        "apt": [],
        "label": "Editor minimap",
        "detect": None,
        "cap": None,
    },
    "gitn": {
        "apt": [],
        "label": "Git integration",
        "detect": "git",
        "cap": None,
    },
    "vapor": {
        "apt": [],
        "label": "Vapor theme",
        "detect": None,
        "cap": None,
    },
    "live_wallpaper": {
        "apt": [],
        "label": "Live matrix wallpaper",
        "detect": None,
        "cap": None,
    },
}


@register_fn(
    "vault.package_installed",
    UseLevel.MEDIUM,
    "Probe dpkg status for one allowlisted package name",
)
def package_installed(pkg: str, *, dpkg_query: str | None = None) -> bool:
    # @use: medium use — purpose: vault probe of apt package install state
    binary = dpkg_query or executable("dpkg-query")
    if not binary or not pkg:
        return False
    run = try_run([binary, "-W", "-f=${Status}", pkg], timeout=2)
    return run.ok and "install ok installed" in run.stdout


@register_fn(
    "vault.feature_row",
    UseLevel.MEDIUM,
    "Build one vault feature row (detect + installable + packages)",
)
def feature_row(feature_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    # @use: medium use — purpose: unify Apps vault card fields from FEATURE_PACKAGES
    apt_pkgs = [str(p) for p in spec.get("apt") or [] if isinstance(p, str) and p]
    detect = spec.get("detect")
    # No detect binary → optional UI-only features count as present when listed.
    detected = True if detect is None else bool(detect and executable(str(detect)))
    installed = all(package_installed(pkg) for pkg in apt_pkgs) if apt_pkgs else detected
    return {
        "id": feature_id,
        "label": str(spec.get("label") or feature_id),
        "apt": apt_pkgs,
        "installable": bool(apt_pkgs),
        "detect": detect,
        "detected": detected,
        "installed": installed,
        "cap": spec.get("cap"),
    }


class VaultAdapter:
    """Allowlisted feature vault — scan catalog; install only via pkexec apt-get."""

    id = "vault"

    def __init__(
        self,
        *,
        pkexec: str | None = None,
        apt_get: str | None = None,
        dpkg_query: str | None = None,
        cache_ttl: float = 5.0,
    ) -> None:
        # Resolve host tools once; tests inject paths / empty strings.
        self.pkexec = pkexec if pkexec is not None else executable("pkexec")
        self.apt_get = apt_get if apt_get is not None else executable("apt-get")
        self.dpkg_query = dpkg_query if dpkg_query is not None else executable("dpkg-query")
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        # Vault catalog is always available; install affordance depends on tools.
        return True

    def snapshot(self) -> dict[str, Any]:
        # @use: high use — purpose: Apps vault poll; feature hashmap for UI cards
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        features = {
            feature_id: feature_row(feature_id, spec)
            for feature_id, spec in FEATURE_PACKAGES.items()
        }
        snapshot = {
            "available": True,
            "backend": "apt",
            "pkexec_available": bool(self.pkexec),
            "apt_available": bool(self.apt_get),
            "can_install": bool(self.pkexec and self.apt_get),
            "features": features,
            "feature_order": list(FEATURE_PACKAGES.keys()),
        }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: vault command dispatch via hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "scan": lambda _payload: self._probe_vault(),
            "probe": lambda _payload: self._probe_vault(),
            "install": lambda payload: self._forge_pack(payload),
            "forge_pack": lambda payload: self._forge_pack(payload),
        }

    def _probe_vault(self) -> dict[str, Any]:
        # @use: medium use — purpose: refresh vault rows after install attempts
        snap = self.snapshot()
        return {"ok": True, **snap}

    def _forge_pack(self, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: explicit confirmed apt install; never silent root
        feature_id = str(payload.get("id") or "").strip()
        spec = FEATURE_PACKAGES.get(feature_id)
        if not spec:
            return command_error("invalid_argument", "unknown vault feature")
        packages = [str(p) for p in spec.get("apt") or [] if isinstance(p, str) and p]
        if not packages:
            return command_error("unavailable", "feature has no apt packages")
        if not self.pkexec or not self.apt_get:
            return command_error("unavailable", "pkexec or apt-get is not available")
        # Packages come only from FEATURE_PACKAGES — never from client strings.
        argv = [self.pkexec, self.apt_get, "install", "-y", "--", *packages]
        run = try_run(argv, timeout=600)
        if not run.ok:
            detail = (run.error or run.stderr or run.stdout or "apt-get failed").strip()[:240]
            return {
                "ok": False,
                "error_code": "internal_error",
                "error": detail or "apt-get failed",
                "packages": packages,
            }
        # Invalidate TTL cache so the next probe sees fresh dpkg state.
        self._cached_snapshot = None
        snap = self.snapshot()
        return {
            "ok": True,
            "id": feature_id,
            "packages": packages,
            "features": snap["features"],
            "can_install": snap["can_install"],
        }
