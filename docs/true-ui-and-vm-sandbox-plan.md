# Toward a "true UI" + a VM sandbox plan

Status: **plan / proposal** (no product code changed by this doc). Follows on from
`docs/interface-design-review.md`. It reviews the most recent build, lists the
elements still needed to turn the control center into a genuine native UI, and
plans a VM sandbox to iterate that UI before we tinker a full one together.

## 0. Where the most recent build stands (v0.6.9, `origin/main`)

The control-center stack is far past a mockup:

- A local **Python stdlib HTTP server** + framework-free Digitalvapor frontend.
- **~18 fail-soft adapters** (audio, display, session, wallpaper, bluetooth,
  notifications, updates, clipboard, capture, vpn, storage, processes, keybinds,
  vault, idle, printers, logs, live_wallpaper) — the A→D "machine-UI gaps" plan
  is **already shipped**.
- Three launch modes: **embedded GTK3 + WebKit2 window**, `--kiosk`, and
  `--browser` fallback.
- Packaging: Debian + FreeBSD, a `share/applications/lmdesktopplus.desktop`
  launcher, a hicolor app icon, and `scripts/install-ui.sh` for user-local installs.

**Verified during this review (on the cloud agent):**

- The **native embedded GTK/WebKit window renders** — after installing WebKitGTK
  (`gir1.2-gtk-3.0`, `gir1.2-webkit2-4.1`) the app launches as a standalone
  window titled "LMDesktopPlus Machine UI" with no browser chrome (screenshot in PR).
- This box has **no `/dev/kvm`**, so the Mint Virt-Manager GUI lab cannot run
  here; the headless TCG smoke guest and the cloud native-window path can.

Conclusion: the backend **feature surface is essentially complete**. "Building up
a true UI" is now mostly **native-shell integration** + **frontend polish**, not
new adapters.

## 1. Next elements needed for a "true UI"

Ranked by leverage. Tier A is small and unblocks everything else.

### A. Native shell / window integration (make it an app, not a page)
- **Window identity — highest priority, currently missing.** `run_gtk()` never
  calls `set_wmclass(...)` and `lmdesktopplus.desktop` has **no
  `StartupWMClass`** (only the live-wallpaper window sets a class). Without this
  the launcher can't be matched to its window: no taskbar grouping, no
  focus-on-relaunch, and Hyprland/Cinnamon window rules can't target it.
- **Single-instance guard.** Relaunching should focus the existing window instead
  of starting a second server + window.
- **App lifecycle polish.** Remember window size/position and last scene; clean
  quit; optional minimize-to-tray.
- **Tray / StatusNotifier + optional autostart** (`~/.config/autostart`) so the
  control center can live as a persistent panel companion.
- **Toolkit currency.** GTK3 + WebKit2 4.0/4.1 today (Mint 22 / Ubuntu 24.04 ship
  4.1). Keep runtime version detection and scope a **GTK4 + WebKitGTK 6.0** path.

### B. Frontend / UX completeness (the "full UI")
- Responsive layout for small windows; consistent **keyboard nav + focus rings**;
  **reduced-motion** honored on every scene (rain/flicker).
- Per-panel **loading / empty / error** states that surface the adapters'
  fail-soft status uniformly.
- Refactor `app.js` into store/bindings as it grows (repo already flags >800 LOC).
- Accessibility pass (aria, dialog focus-trap) across all scenes, not just dialogs.

### C. Desktop integration depth
- First-run/onboarding that applies wallpaper + generated GTK/Hypr overlays and
  offers the Hyprland session arm. (Pieces exist; wire them into a guided flow.)

### D. Distribution & trust
- Symbolic/tray icon variants and store/AppStream screenshots; reproducible deb.
  CI already runs `./tests/run-all.sh`.

## 2. Why a VM sandbox is required first

A true UI can only be judged on a real **Mint Cinnamon** (and optionally
Hyprland) desktop: login greeter and sessions, GTK theme + generated overlays,
wallpaper via `gsettings`, taskbar/window rules matching the WM class, tray, and
the real audio/brightness/bluetooth/network adapters. A headless or cloud box
cannot exercise those. The cloud native-window run above proves the *shell*
renders, but on Ubuntu without the Cinnamon integration.

## 3. VM sandbox plan (leverage what exists, add the gaps)

Two tracks, matched to where development happens.

### Track 1 — KVM host: full Mint Cinnamon GUI lab (already built)
Use the existing `scripts/vm/{create,attach,destroy}-mint-guest.sh` +
`docs/vm-lab.md`.

- Host prereqs: `qemu-kvm`, `libvirt`, `virt-manager`; user in `kvm`/`libvirt`.
- Flow: create guest from a Mint ISO → install → virtiofs-share the repo at
  `/mnt/lmdesktopplus` → `./install.sh` + `./scripts/install-ui.sh` → snapshot
  `clean-rice` → hotswap-iterate; destroy/recreate to reset.
- **This is where the true UI gets built and seen.** Best on a dev
  laptop/workstation with KVM.
- Add for UI iteration:
  - An `--autostart-ui` option (or doc step) so a fresh guest boots straight into
    the control center via an autostart entry.
  - Optional unattended Mint install (preseed/cloud-init) to remove manual
    installer clicks (currently a documented non-goal).
  - Optional in-guest Hyprland session for the tiling variant.

### Track 2 — No-KVM / cloud agent: headless smoke + screenshot regression
- `scripts/vm/smoke-cloud-guest.sh` (QEMU **TCG** + cloud-init + 9p) already runs
  `./tests/run-all.sh` in a clean guest — keep it for packaging/adapter/unit
  validation in CI and on cloud agents. It is **not** a GUI.
- To actually *see* the UI without KVM:
  1. **Native window on the cloud X display** (validated here): install WebKitGTK,
     run `lmdesktopplus`, screenshot/record. Fast; exercises the native shell +
     frontend (Ubuntu, not Mint).
  2. **Xvfb + native window** for **automated screenshot regression** of each
     scene — cheap CI artifact, no KVM required.
  3. A TCG Mint/Cinnamon guest over VNC/Spice is possible but too slow for UX
     work — not recommended.

### Concrete sandbox deliverables to build next (small)
1. `scripts/vm/run-ui-guest.sh` (or `create-mint-guest.sh --autostart-ui`) — boot
   a Mint guest that auto-launches the control center for UX iteration.
2. `tests/ui-screenshot.sh` — Xvfb-boot the native window and capture each scene
   (UI regression that works without KVM; WebKitGTK confirmed available).
3. `docs/vm-lab.md` addendum "Iterating the true UI" documenting both tracks plus
   the cloud native-window recipe proven in this review.

## 4. Sequencing (before tinkering a full UI)

1. Land Tier-A window identity (`set_wmclass` + `StartupWMClass` + single-instance)
   — tiny, unblocks window matching and automated UI testing.
2. Stand up the sandbox: Track 1 on the dev host; add the Xvfb screenshot smoke
   (Track 2) to CI.
3. Iterate frontend polish (Tier B) against the sandbox with screenshot regressions.
4. Distribution polish (Tier D) last.

## 5. Risks / open questions

- **Toolkit migration** (GTK4 + WebKit 6.0) vs staying on 4.1 — decide against the
  target Mint release; keep the existing runtime version fallback either way.
- **No practical cloud GUI**: TCG Cinnamon is too slow, so faithful UX iteration
  needs a **KVM host**. If the team lacks one, UX work stays manual on a Mint box
  while CI uses the Xvfb native-window screenshots.
- **Tray/single-instance** add moderate native code; keep the `--browser`
  fallback intact for headless environments.

Suggested next step: approve Tier-A + the two sandbox deliverables (autostart-UI
guest + Xvfb screenshot smoke), then start the frontend-polish loop.
