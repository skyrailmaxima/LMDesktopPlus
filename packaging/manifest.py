#!/usr/bin/env python3
"""Parser + CLI for the canonical LMDesktopPlus software manifest.

The manifest (``software-manifest.json``, next to this file) is the single
source of truth for the peer software the UI drives, the rice packages, and the
vapor//matrix fonts. Build scripts shell out to this CLI instead of hardcoding
package lists, so the main ``.deb``, the ``lmdesktopplus-desktop`` metapackage,
and the FreeBSD metaport all stay in sync.

Stdlib only (no PyYAML / third-party deps), matching the project convention.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent / "software-manifest.json"

VALID_TIERS = ("core", "recommended", "optional", "rice", "font")
VALID_SOURCES = ("distro", "ofl-fetch")

# Tier -> Debian control field for the MAIN lmdesktopplus package.
MAIN_FIELD_TIERS = {
    "Depends": ("core",),
    "Recommends": ("recommended",),
    "Suggests": ("optional",),
}


def load(path: Path = MANIFEST_PATH) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    components = data.get("components")
    if not isinstance(components, list):
        raise ValueError("manifest 'components' must be a list")
    return components


def _check(components: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, comp in enumerate(components):
        cid = comp.get("id")
        where = cid or f"#{index}"
        if not cid or not isinstance(cid, str):
            errors.append(f"{where}: missing/invalid id")
        elif cid in seen:
            errors.append(f"{cid}: duplicate id")
        else:
            seen.add(cid)
        if comp.get("tier") not in VALID_TIERS:
            errors.append(f"{where}: invalid tier {comp.get('tier')!r}")
        if comp.get("source") not in VALID_SOURCES:
            errors.append(f"{where}: invalid source {comp.get('source')!r}")
        if "debian" not in comp or "freebsd" not in comp:
            errors.append(f"{where}: missing debian/freebsd field")
        if comp.get("source") == "distro" and not comp.get("debian") and not comp.get("freebsd"):
            errors.append(f"{where}: distro component has no debian or freebsd package")
        if comp.get("source") == "ofl-fetch" and (comp.get("debian") or comp.get("freebsd")):
            errors.append(f"{where}: ofl-fetch component should not carry a distro package")
    return errors


def debian_field(components: list[dict], field: str) -> str:
    tiers = MAIN_FIELD_TIERS[field]
    entries = [c["debian"] for c in components if c.get("tier") in tiers and c.get("debian")]
    return ", ".join(entries)


def debian_metapackage_depends(components: list[dict]) -> list[str]:
    """Every distro-sourced component with a Debian package (all tiers)."""
    return [c["debian"] for c in components if c.get("source") == "distro" and c.get("debian")]


def freebsd_packages(components: list[dict]) -> list[str]:
    return [c["freebsd"] for c in components if c.get("source") == "distro" and c.get("freebsd")]


def _cmd_check(components: list[dict], _args) -> int:
    errors = _check(components)
    if errors:
        for err in errors:
            print(f"manifest: {err}", file=sys.stderr)
        return 1
    print(f"software-manifest OK ({len(components)} components)")
    return 0


def _cmd_deb_field(components: list[dict], args) -> int:
    print(debian_field(components, args.field))
    return 0


def _cmd_deb_metapackage(components: list[dict], _args) -> int:
    print(", ".join(debian_metapackage_depends(components)))
    return 0


def _cmd_freebsd(components: list[dict], _args) -> int:
    print(" ".join(freebsd_packages(components)))
    return 0


def _cmd_list(components: list[dict], args) -> int:
    rows = [c for c in components if not args.tier or c.get("tier") == args.tier]
    width = max((len(c["id"]) for c in rows), default=0)
    for comp in rows:
        deb = comp.get("debian") or "-"
        bsd = comp.get("freebsd") or "-"
        print(f"{comp['id']:<{width}}  {comp['tier']:<11}  deb:{deb:<40}  freebsd:{bsd}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="validate the manifest")
    p_field = sub.add_parser("deb-field", help="print a main-package control field")
    p_field.add_argument("field", choices=sorted(MAIN_FIELD_TIERS))
    sub.add_parser("deb-metapackage-depends", help="print the full metapackage Depends set")
    sub.add_parser("freebsd-packages", help="print the FreeBSD pkg set")
    p_list = sub.add_parser("list", help="human-readable component table")
    p_list.add_argument("--tier", choices=VALID_TIERS)

    args = parser.parse_args(argv)
    components = load(args.manifest)

    dispatch = {
        "check": _cmd_check,
        "deb-field": _cmd_deb_field,
        "deb-metapackage-depends": _cmd_deb_metapackage,
        "freebsd-packages": _cmd_freebsd,
        "list": _cmd_list,
    }
    return dispatch[args.command](components, args)


if __name__ == "__main__":
    raise SystemExit(main())
