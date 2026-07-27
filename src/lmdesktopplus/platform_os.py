"""OS family detection for Linux / FreeBSD UI builds.

Adapters and samplers branch on `os_family()` so Linux Mint remains the
primary rice target while FreeBSD can ship the vapor//matrix UI package.
"""

from __future__ import annotations

import platform

from .fncache import UseLevel, register_fn

FAMILY_LINUX = "linux"
FAMILY_FREEBSD = "freebsd"
FAMILY_OTHER = "other"

_cached_family: str | None = None


def _detect_family() -> str:
    system = platform.system().lower()
    if system == "linux":
        return FAMILY_LINUX
    if system in {"freebsd", "dragonfly", "midnightbsd"}:
        return FAMILY_FREEBSD
    # Other *BSD with "bsd" in the name (exclude Open/Net unless we add backends).
    if "bsd" in system and system not in {"openbsd", "netbsd"}:
        return FAMILY_FREEBSD
    return FAMILY_OTHER


@register_fn(
    "platform_os.os_family",
    UseLevel.HIGH,
    "Return linux|freebsd|other for backend dispatch",
)
def os_family() -> str:
    # @use: high use — purpose: one-shot OS gate for metrics/actions backends
    global _cached_family
    if _cached_family is None:
        _cached_family = _detect_family()
    return _cached_family


def clear_os_family_cache() -> None:
    """Test helper — reset cached family after mocking platform.system."""
    global _cached_family
    _cached_family = None


def is_linux() -> bool:
    return os_family() == FAMILY_LINUX


def is_freebsd() -> bool:
    return os_family() == FAMILY_FREEBSD


def is_bsd_family() -> bool:
    # @use: medium use — purpose: soft-gate Linux-only tools (bwrap, nmcli, apt)
    return os_family() == FAMILY_FREEBSD or platform.system().lower() in {
        "freebsd",
        "openbsd",
        "netbsd",
        "dragonfly",
    }
