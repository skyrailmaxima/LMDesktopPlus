# Host adapters

LMDesktopPlus isolates host-specific machine controls behind small adapters. The
registry is keyed by a stable adapter ID, and `/api/v1/state` exposes each
adapter's cached snapshot under `adapters.<id>`.

## Contract

Each adapter implements:

```python
class Adapter(Protocol):
    id: str
    def available(self) -> bool: ...
    def snapshot(self) -> dict[str, Any]: ...
    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]: ...
```

`snapshot()` must be cheap, cached when it invokes a process, and return
`{"available": false}` instead of raising when its host integration is absent.
Commands accept only adapter-defined names and validated payloads. Unknown
commands return an error; adapters never expose arbitrary shell execution.

Commands use `POST /api/v1/adapter/<id>` with a JSON body such as:

```json
{"name": "set_volume", "payload": {"volume": 50}}
```

The server accepts API calls only from loopback clients carrying the per-launch
`X-LMDP-Token`. Command implementations pass argument arrays directly to the
process runner and clamp or reject user-controlled values.

## Stage A matrix

| Adapter | Preferred integration | Fallback | Commands | Missing-tool behavior |
|---|---|---|---|---|
| `audio` | `wpctl` (WirePlumber) | `pactl` (PulseAudio) | `set_volume` (0–100), `toggle_mute` | Unavailable; UI shows installation guidance |
| `display` | `brightnessctl` | `/sys/class/backlight` read-only snapshot | `set_brightness` (1–100) when writable | Unavailable, or read-only when sysfs is readable |
| `session` | `HYPRLAND_INSTANCE_SIGNATURE`, `XDG_CURRENT_DESKTOP` | One-shot flag at `~/.local/share/lmdesktopplus/start-hyprland-once` | `status`, `arm_hyprland` | Always available; arming writes only the flag |
| `wallpaper` | Cinnamon `gsettings` | `hyprctl hyprpaper` for raster files | `list`, `apply` by catalog ID | Catalog remains visible; apply fails softly if no backend succeeds |

Audio and display probes use a 0.75-second TTL. Wallpaper entries come from the
packaged assets and `~/.local/share/lmdesktopplus/wallpapers/`; the UI addresses
them through the wallpaper hash map rather than accepting arbitrary paths.

`/api/v1/state` also emits `assets_revision`, a short hash of the icon and
wallpaper catalogs. The frontend `AssetMap` rebuilds its hash tables only when
that revision changes, keeping wallpaper picker updates cheap.

## Digitalvapor chrome

Stage A controls reuse packaged Digitalvapor primitives (`dv-slider`,
`dv-progress`, `dv-bar__stat`, `dv-choice`, `dv-tag`, `dv-btn`) from
`static/digitalvapor.css`. The bundled `Digitalvapor - Styleguide (2).html`
export matches the prior styleguide content (UUID remaps only); icons for Stage
A live under `static/icons/` rather than inside that HTML pack.

## Planned optional integrations

These binaries are optional suggestions, not hard package dependencies:

| Concern | Preferred tools | Fallback or limitation |
|---|---|---|
| Bluetooth | `bluetoothctl` | Adapter unavailable without BlueZ tools |
| Notifications | `gdbus`, `notify-send` | Some desktops do not expose notification history |
| Updates | `mintupdate` | `apt` for a cached upgradable count |
| Clipboard | `wl-paste`, `wl-copy` | `xclip` on X11 |
| Screenshots | `grim`, optionally `slurp` | `gnome-screenshot` on Cinnamon |
| VPN | `nmcli` | No credentials are stored by LMDesktopPlus |
| Removable storage | `lsblk`, `udisksctl` | Operations remain device-allowlisted |

Adapters must continue to fail soft across Cinnamon and Hyprland sessions. A
binary being present is not sufficient: non-zero exits and timeouts are
reported through `last_error` or command errors without breaking state polling.
