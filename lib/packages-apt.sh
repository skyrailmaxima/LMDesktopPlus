APT_SHARED=(
  kitty rofi tmux btop curl wget git
  fonts-jetbrains-mono python3 python3-gi gir1.2-gtk-3.0
  playerctl bubblewrap
)

APT_HYPR_OPTIONAL=(waybar swaybg)

install_apt_packages() {
  local extras=("$@")
  local pkgs=("${APT_SHARED[@]}" "${extras[@]}")
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    log_info "DRY_RUN apt install: ${pkgs[*]}"
    return 0
  fi
  sudo apt-get update
  sudo apt-get install -y "${pkgs[@]}"

  # Mint/Ubuntu releases expose WebKitGTK introspection as either 4.1 or 4.0.
  # Install the first available package instead of making the whole install
  # fail because one exact ABI name is absent.
  local webkit_pkg=""
  for candidate in gir1.2-webkit2-4.1 gir1.2-webkit2-4.0; do
    if apt-cache show "$candidate" >/dev/null 2>&1; then
      webkit_pkg="$candidate"
      break
    fi
  done
  if [[ -n "$webkit_pkg" ]]; then
    sudo apt-get install -y "$webkit_pkg"
  else
    log_warn "No WebKitGTK GIR package found; LMDesktopPlus UI will use browser fallback"
  fi
}
