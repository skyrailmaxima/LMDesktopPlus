# AGENTS.md

## Cursor Cloud specific instructions

LMDesktopPlus is a **Linux Mint rice** (`install.sh`) plus a **Python machine UI**
(`src/lmdesktopplus`, GTK/WebKit or `--browser`). The installer symlinks shared
configs, fetches fonts, and applies Cinnamon `gsettings`; the UI is an
installable local control center. Runtime for tests: `bash`, `python3` (≥3.10),
optional `node`, and `dpkg-deb` for package checks.

### Lint
- Primary linter is **shellcheck** (the scripts contain `# shellcheck` directives). It is not required to run the app and is not in the update script; install it on demand with `sudo apt-get install -y shellcheck`.
- Lint the entrypoints so sourced libraries are followed in-context: `shellcheck -x install.sh uninstall.sh scripts/*.sh`. Do **not** run bare `shellcheck lib/*.sh` — those files are sourced (no shebang) and will report spurious `SC2148`.
- Zero-dependency syntax check that always works: `for f in install.sh uninstall.sh lib/*.sh scripts/*.sh tests/*.sh; do bash -n "$f"; done`.
- Known/intentional shellcheck items in `uninstall.sh` (do not "fix"): `SC2034` on `--cinnamon-only` (kept for CLI symmetry, per code comment) and `SC2317` on the `maybe()` helper (false-positive unreachable).

### Test
- Full suite (what GitHub Actions runs): `./tests/run-all.sh`
  - structure / common / frontend assets / stow
  - `PYTHONPATH=src python3 -m unittest discover -s tests/python -v`
  - optional `node --check` on static JS
  - `./install.sh --dry-run --cinnamon-only`
  - Debian package build + content checks
  - FreeBSD UI tarball stage + no root `/plist` check
  - `./scripts/collapse-stack.sh` dry-run
- Narrow: `bash tests/smoke-structure.sh`, `bash tests/test-common.sh`
- CI workflow: `.github/workflows/ci.yml` on `main` / `feature/lmdesktopplus`
  (push + pull_request). Status check name: **test (ubuntu)**.
- Post-review trunk collapse: [`docs/collapse-trunk.md`](docs/collapse-trunk.md)

### Run
- Machine UI (no display needed for server/API tests): `PYTHONPATH=src python3 -m lmdesktopplus --browser`
- Safe installer plan: `./install.sh --dry-run`
- This VM is **Ubuntu (Debian-family)**, not Mint, so `install.sh` prints a warning and continues. On a truly unsupported OS use `FORCE=1 ./install.sh`.
- To exercise the real installer end-to-end **without touching this VM**, point `HOME` at a sandbox dir and stub `sudo`/`apt-get` on `PATH`, then run `./install.sh --cinnamon-only`.
- Fail-soft behaviors that are expected here (not errors): no SVG rasterizer so no PNG is produced; `gsettings` fails without Cinnamon; Hyprland not on `PATH` so its setup is skipped.
- The **themed rice desktop** (Cinnamon/Hyprland session) can't run here, but the **machine UI window itself renders fine** and can be verified two ways: (1) headless screenshots of each scene via `bash tests/ui-screenshot.sh` (Xvfb + the real GTK/WebKit shell; runs as the optional stage in `run-all.sh`), and (2) an interactive/recorded demo on the VM's VNC display `:1` — launch with `DISPLAY=:1 PYTHONPATH=src python3 -m lmdesktopplus` (point `XDG_*` at a scratch dir for clean state). The lock screen unlocks with any click. Verification is otherwise via installer logs, unit tests, and CI artifacts (`.deb` / FreeBSD `.txz`).

### Frontend (machine UI web assets)
- The UI is framework-free classic JS loaded in order in `static/index.html`: `digitalvapor.js → bindings.js → store.js → tiles.js → app.js`. Scripts share one global scope, so `tiles.js` can call `app.js` globals (e.g. `esc`) at render time.
- Adding a new `static/*.js` file requires registering it in **three** places or tests fail: the `<script>` tag in `static/index.html`, the `allowed_static` allowlist in `server.py`, and the asset greps in `tests/frontend-assets.sh` / `tests/run-all.sh`.
- User customization (editable greeting/titles + per-tile view/order/hidden layout) is persisted in the validated `customization` namespace in `settings.json` via `POST /api/v1/settings` — there are no new endpoints. Frontend `GREETING_MODES` mirrors `config.py`; keep them in sync.
