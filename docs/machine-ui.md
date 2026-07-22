# LMDesktopPlus machine UI

The machine UI is a local Linux application that complements Cinnamon or
Hyprland. It does not replace the desktop environment or expose a remote
management service.

## Launch

```bash
lmdesktopplus
lmdesktopplus --kiosk
lmdesktopplus --browser
```

## Architecture

```text
GTK3 + WebKit2, or browser fallback
             │
             │ HTTP on 127.0.0.1, random port
             │ per-launch X-LMDP-Token
             ▼
Python ThreadingHTTPServer
  ├── settings and agent registry
  ├── /proc and sysfs sampler
  ├── allowlisted application/system actions
  ├── NetworkManager adapter
  ├── playerctl adapter
  ├── GTK/Hyprland overlay generator
  └── scoped agent launcher
```

The launch token is inserted into a metadata field rather than an inline
script, allowing the frontend to retain a restrictive `script-src 'self'`
Content Security Policy.

## Implemented surfaces

| Surface | Functional implementation |
|---|---|
| Lock scene | Internal UI lock plus allowlisted system lock |
| Desktop | Host identity, metrics, quick launch, media, and agents |
| Agent terminal | Dedicated homes, workspaces, command detection, optional Bubblewrap |
| tmux | Attach or create the stable `lmdesktopplus` session |
| Editor | Detect and launch supported editors against `~/work` |
| Browser | Detect and launch a browser while retaining agent controls |
| Rofi | Launch the shared application theme |
| Dotfiles | Display package/config paths and open configuration folders |
| Monitor | Live metrics and rolling charts |
| App vault | Persistent feature switches and capability badges |
| Settings | Appearance, behavior, network, agents, keybinds, and boundaries |
| Network | Themed scan, password modal, connect, and disconnect workflow |
| Media | MPRIS state and controls |
| UI Kit | Live Digitalvapor components and interaction tests |

## Digitalvapor layer

The 0.3.0 frontend uses a reusable, font-free component library derived from
the expanded Digitalvapor styleguide. New panel features should be prototyped
in the UI Kit and built from the shared components rather than introducing
one-off colors, borders, modal code, or notification code.

See [`digitalvapor-design-system.md`](digitalvapor-design-system.md).

## Agent registry

Definitions live at:

```text
~/.config/lmdesktopplus/agents.json
```

Each agent receives a persistent home under:

```text
~/.local/share/lmdesktopplus/agents/<name>
```

When enabled and available, Bubblewrap mounts system paths read-only and only
the selected agent home and workspace writable. Network access is controlled
per agent. This is useful isolation, not a complete virtual machine boundary.

## Appearance settings

Settings are stored in:

```text
~/.config/lmdesktopplus/settings.json
```

Changes update Digitalvapor runtime tokens and generate:

```text
~/.config/gtk-3.0/lmdesktopplus-generated.css
~/.config/gtk-4.0/lmdesktopplus-generated.css
~/.config/lmdesktopplus/hypr-generated.conf
```

## Debian package

```bash
./packaging/build-deb.sh
sudo apt install ./dist/lmdesktopplus_0.4.2_all.deb
```

The Debian package contains the machine UI. Run `install.sh` from the source
repository for the complete Cinnamon/Hyprland rice.

## Development

```bash
PYTHONPATH=src python3 -m lmdesktopplus --browser
./tests/run-all.sh
```
