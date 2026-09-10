"""Runtime GTK/WebKit toolkit selection.

The embedded UI prefers the modern GTK4 + WebKitGTK 6.0 stack when it is
installed, and otherwise falls back to GTK3 + WebKit2 (4.1, then 4.0). The
selection is done by *probing* available typelib versions with
``gi.Repository.enumerate_versions`` — this never commits the process to a
version (unlike ``gi.require_version``), so callers can decide before importing
any ``gi.repository`` module.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Toolkit:
    gtk_version: str
    webkit_namespace: str
    webkit_version: str

    @property
    def is_gtk4(self) -> bool:
        return self.gtk_version.startswith("4")


# Preference order: (Gtk version, WebKit namespace, WebKit version).
TOOLKIT_PREFERENCES: tuple[tuple[str, str, str], ...] = (
    ("4.0", "WebKit", "6.0"),
    ("3.0", "WebKit2", "4.1"),
    ("3.0", "WebKit2", "4.0"),
)


def _available_versions(namespace: str) -> set[str]:
    """Return typelib versions available for ``namespace`` (empty if none)."""
    try:
        from gi import Repository  # imported lazily so tests can stub the module
    except Exception:  # noqa: BLE001 — pygobject missing entirely
        return set()
    try:
        return set(Repository.get_default().enumerate_versions(namespace))
    except Exception:  # noqa: BLE001 — unknown namespace / broken introspection
        return set()


def available_toolkits(available=_available_versions) -> list[Toolkit]:
    """Return every installed toolkit in preference order (best first)."""
    gtk_versions = available("Gtk")
    found: list[Toolkit] = []
    for gtk_version, webkit_namespace, webkit_version in TOOLKIT_PREFERENCES:
        if gtk_version in gtk_versions and webkit_version in available(webkit_namespace):
            found.append(Toolkit(gtk_version, webkit_namespace, webkit_version))
    return found


def select_toolkit(available=_available_versions) -> Toolkit | None:
    """Pick the best available toolkit, or ``None`` when GTK/WebKit is absent."""
    toolkits = available_toolkits(available)
    return toolkits[0] if toolkits else None
