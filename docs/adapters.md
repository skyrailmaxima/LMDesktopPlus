# Host adapters

LMDesktopPlus isolates host-specific machine controls behind small adapters. The
registry is keyed by a stable adapter ID. Clients can poll the aggregate
`/api/v1/state` payload or refresh individual domains:

| Endpoint | Contents |
|---|---|
| `/api/v1/state` / `/api/v1/state/full` | Aggregate snapshot (compat) |
| `/api/v1/state/core` | Version, identity, settings, accents, agents, capabilities |
| `/api/v1/state/metrics` | System sampler |
| `/api/v1/state/adapters` | All adapter envelopes |
| `/api/v1/state/network` | NetworkManager current connection |
| `/api/v1/state/media` | MPRIS / media status |
| `/api/v1/state/assets` | Icon/wallpaper catalogs + revision |

## Contract

Each adapter implements:

```python
class Adapter(Protocol):
    id: str
    def available(self) -> bool: ...
    def snapshot(self) -> dict[str, Any]: ...
    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]: ...
```

### Snapshot envelope

`snapshot()` must be cheap, cached when it invokes a process, and return
`{"available": false}` instead of raising when its host integration is absent.
The registry normalizes every snapshot into a typed envelope:

```json
{
  "id": "session",
  "available": true,
  "status": "armed",
  "backend": null,
  "updated_at": 1710000000.0,
  "stale": false,
  "capabilities": ["arm_once", "disarm", "status", "verify_configuration"],
  "state": { "...": "adapter-specific fields" },
  "error": null,
  "hyprland_active": false
}
```

Flat adapter fields remain for one release so older UI code keeps working; new
UI should prefer `status`, `capabilities`, and `state`.

`status` values include `ready`, `unavailable`, `degraded`, `error`, and for
session lifecycle: `not_installed`, `armed`, `active`.

### Commands and error codes

Commands accept only adapter-defined names and validated payloads. Unknown
commands return an error; adapters never expose arbitrary shell execution.

Commands use `POST /api/v1/adapter/<id>` with a JSON body such as:

```json
{"name": "set_volume", "payload": {"volume": 50}}
```

Failures return JSON shaped like:

```json
{"ok": false, "error_code": "timeout", "error": "Adapter command failed"}
```

Stable `error_code` values: `unavailable`, `invalid_argument`, `permission_denied`,
`timeout`, `internal_error`. Uncaught adapter exceptions are classified at the
HTTP boundary; raw exception text is logged server-side and not returned by
default.

### Auth and origin checks

The server accepts API calls only from loopback clients carrying the per-launch
`X-LMDP-Token`. In addition it rejects foreign `Origin` values and
`Sec-Fetch-Site: cross-site` requests. Command implementations pass argument
arrays directly to the process runner and clamp or reject user-controlled values.

Cache loaders use per-key locks so a slow host probe cannot block unrelated
state domains.

## Stage A matrix

| Adapter | Preferred integration | Fallback | Commands | Missing-tool behavior |
|---|---|---|---|---|
| `audio` | `wpctl` (WirePlumber) | `pactl` (PulseAudio) | `set_volume` (0–100), `toggle_mute` | Unavailable; UI shows installation guidance |
| `display` | `brightnessctl` | `/sys/class/backlight` read-only snapshot | `set_brightness` (1–100) when writable | Unavailable, or read-only when sysfs is readable |
| `session` | `HYPRLAND_INSTANCE_SIGNATURE`, `XDG_CURRENT_DESKTOP` | One-shot flag at `~/.local/share/lmdesktopplus/start-hyprland-once` | `status` / `verify_configuration`, `arm_once` (`arm_hyprland` alias), `disarm` | Always available; arming writes only the flag and does not log out of Cinnamon |
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

## Stage B matrix

| Adapter | Preferred integration | Fallback | Commands | TTL | Missing-tool behavior |
|---|---|---|---|---|---|
| `bluetooth` | `bluetoothctl` | none | `power`, `scan`, `connect`, `disconnect` | 5s | Unavailable without BlueZ tools; Blocked power hints `rfkill` |
| `notifications` | `notify-send` + Cinnamon `gsettings` DND | local `behavior.do_not_disturb` | `send_test`, `set_dnd` | 5s | Always available for DND; send requires `notify-send` (no history API) |
| `updates` | `apt list --upgradable` | — | `refresh`, `open` (`mintupdate`) | 600s | Unavailable without `apt`; open disabled without Mint Update |
| `clipboard` | `wl-paste` / `wl-copy` (Wayland) | `xclip` (X11) | `peek`, `copy`, `clear`, `history` (RAM only) | 2s | Unavailable without a session-matched tool; never writes clipboard to disk |
| `capture` | `grim` (+ `slurp` region) | `gnome-screenshot` | `full`, `region`, `open_folder` | 60s capability | Unavailable without tools; saves only under `~/Pictures/lmdesktopplus/` |

## Optional Suggests (not hard Depends)

| Concern | Preferred tools | Notes |
|---|---|---|
| Bluetooth | `bluez`, `bluez-utils` | Provides `bluetoothctl` |
| Notifications | `libnotify-bin` | Provides `notify-send` |
| Clipboard | `wl-clipboard`, `xclip` | Session-routed |
| Screenshots | `grim`, `slurp`, `gnome-screenshot` | Hyprland vs Cinnamon |
| Updates | `mintupdate` | Launcher only; counting uses `apt` |

## Stage C+ (still planned)

| Concern | Preferred tools | Fallback or limitation |
|---|---|---|
| VPN | `nmcli` | No credentials are stored by LMDesktopPlus |
| Removable storage | `lsblk`, `udisksctl` | Operations remain device-allowlisted |

Adapters must continue to fail soft across Cinnamon and Hyprland sessions. A
binary being present is not sufficient: non-zero exits and timeouts are
reported through `error` / `error_code` or command errors without breaking
state polling.
