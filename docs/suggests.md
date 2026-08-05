# Optional Suggests (tidy map)

Debian `Suggests` are optional host tools. LMDesktopPlus never hard-Depends on
them; adapters fail soft and the Apps vault can `pkexec`-install allowlisted
packages after confirm.

Source of packaging truth: `packaging/build-deb.sh` `Suggests:` line.
This doc maps each Suggest → consumer so the list stays intentional.

| Suggest | Binary / role | Consumed by |
|---|---|---|
| `hyprland` | Hyprland compositor | session arm, live wallpaper rules |
| `waybar` | status bar | vault `waybar`, hypr session |
| `bluez` | `bluetoothctl` | `bluetooth` adapter / vault |
| `starship` | prompt | vault `starship`, shared config |
| `policykit-1` | `pkexec` | `vault` installs |
| `grim` | screenshot | `capture` (Wayland) |
| `slurp` | region select | `capture` region |
| `wl-clipboard` | `wl-copy` / `wl-paste` | `clipboard` (Wayland) |
| `xclip` | X11 clipboard | `clipboard` (X11) |
| `libnotify-bin` | `notify-send` | `notifications` |
| `mintupdate` | Mint Update UI | `updates` open |
| `cups-client` | `lpstat` | `printers` |
| `system-config-printer` | printer settings UI | `printers` open |
| `swayidle` | idle daemon | `idle` generated script |
| `mpvpaper` | video wallpaper | `live_wallpaper` optional backend |

## Recommends (stronger than Suggests)

From `packaging/build-deb.sh`: `kitty`, `rofi`, `tmux`, `btop`, `playerctl`,
`bubblewrap` — common daily-driver tools the UI launches or detects.

## Adding a Suggest

1. Wire the adapter to fail soft without the binary.
2. Add the package to `Suggests:` in `packaging/build-deb.sh`.
3. Add a row here and, if installable from the vault, a `FEATURE_PACKAGES` entry.
4. Prefer a UI kit story for any new Settings/Monitor control (Task 23).
