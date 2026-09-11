# Software manifest

`packaging/software-manifest.json` is the single source of truth for **all
packaged software** shipped with LMDesktopPlus: the peer tools the control
center drives fail-soft, the Linux Mint rice packages, and the vapor//matrix
fonts. Everything that needs a package list reads it through
`packaging/manifest.py` instead of hardcoding names, so the main `.deb`, the
`lmdesktopplus-desktop` metapackage, and the FreeBSD metaport never drift.

## Component fields

| field | meaning |
| --- | --- |
| `id` | stable logical name |
| `tier` | `core`, `recommended`, `optional`, `rice`, or `font` |
| `source` | `distro` (OS package manager) or `ofl-fetch` (font fetched by `scripts/fetch-fonts.sh`) |
| `debian` | apt dependency spec (may include a version or `\|` alternates), or `null` |
| `freebsd` | FreeBSD pkg name, or `null` when not applicable |
| `category` | grouping for humans/docs |
| `description` | short human description |

## Tier → package mapping

For the **main `lmdesktopplus` package**:

- `core` → `Depends`
- `recommended` → `Recommends`
- `optional` → `Suggests`

The **`lmdesktopplus-desktop` metapackage** `Depends` on every `distro`
component that has a Debian package (all tiers), so preinstalling it on the
Mint respin pulls the entire software set. `ofl-fetch` fonts have no distro
package and are fetched at install time.

## CLI

```sh
python3 packaging/manifest.py check                     # validate the manifest
python3 packaging/manifest.py deb-field Depends         # main-package control field
python3 packaging/manifest.py deb-metapackage-depends   # full metapackage Depends
python3 packaging/manifest.py freebsd-packages          # FreeBSD pkg set
python3 packaging/manifest.py list [--tier optional]    # human-readable table
```

`packaging/build-deb.sh` consumes `deb-field`; the desktop metapackage build
consumes `deb-metapackage-depends`; the FreeBSD metaport tooling consumes
`freebsd-packages`. `./tests/run-all.sh` runs `manifest check` and the
`tests/python/test_software_manifest.py` regression lock.
