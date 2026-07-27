# AGENTS.md

## Cursor Cloud specific instructions

LMDesktopPlus is a pure **Bash** project (a Linux Mint Cinnamon + optional
Hyprland desktop "rice"/theming installer). There is **no language package
manager, no lockfile, no build step, and no long-running service** — the
"product" is `install.sh` (with `uninstall.sh`), which symlinks shared configs
into `~/.config/...`, fetches fonts, materializes a wallpaper/palette, and
applies Cinnamon `gsettings`. Runtime deps are just `bash` + coreutils, already
present on the VM.

### Lint
- Primary linter is **shellcheck** (the scripts contain `# shellcheck` directives). It is not required to run the app and is not in the update script; install it on demand with `sudo apt-get install -y shellcheck`.
- Lint the entrypoints so sourced libraries are followed in-context: `shellcheck -x install.sh uninstall.sh scripts/*.sh`. Do **not** run bare `shellcheck lib/*.sh` — those files are sourced (no shebang) and will report spurious `SC2148`.
- Zero-dependency syntax check that always works: `for f in install.sh uninstall.sh lib/*.sh scripts/*.sh tests/*.sh; do bash -n "$f"; done`.
- Known/intentional shellcheck items in `uninstall.sh` (do not "fix"): `SC2034` on `--cinnamon-only` (kept for CLI symmetry, per code comment) and `SC2317` on the `maybe()` helper (false-positive unreachable).

### Test
- `bash tests/smoke-structure.sh` — asserts expected files exist (prints `structure OK`).
- `bash tests/test-common.sh` — unit-tests `lib/common.sh` symlink/backup logic in a temp HOME (prints `common OK`).

### Run
- Safe plan, changes nothing: `./install.sh --dry-run`.
- This VM is **Ubuntu (Debian-family)**, not Mint, so `install.sh` prints a warning and continues. On a truly unsupported OS use `FORCE=1 ./install.sh`.
- To exercise the real installer end-to-end **without touching this VM**, point `HOME` at a sandbox dir and stub `sudo`/`apt-get` on `PATH`, then run `./install.sh --cinnamon-only` (the `apt`/`sudo` steps are the only ones that would mutate the system; everything else writes only under the sandbox `HOME`). `uninstall.sh` then rolls the sandbox back.
- Fail-soft behaviors that are expected here (not errors): no SVG rasterizer (`convert`/`rsvg-convert`/`inkscape` absent) so no PNG is produced; `gsettings` fails with "No such schema" / no D-Bus (no Cinnamon session); Hyprland not on `PATH` so its setup is skipped.
- There is no GUI/display server on the VM, so the themed desktop itself cannot be rendered here — verification is done via the installer logs and the created symlinks.
