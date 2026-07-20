APT_SHARED=(
  kitty rofi tmux btop curl wget git
  fonts-jetbrains-mono
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
}
