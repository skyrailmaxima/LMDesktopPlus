#!/usr/bin/env bash
# Best-effort Hyprland install for Linux Mint / Ubuntu-family hosts.
# Does NOT replace Cinnamon; only installs the compositor + portal so
# LMDesktopPlus can register a Wayland session afterward.
#
# Note: ppa:cppiber/hyprland is a community PPA (not Canonical/Hyprland
# official). Packaging can lag or drop series — see docs/install-notes.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/lib/common.sh"

DRY_RUN="${DRY_RUN:-0}"

hypr_on_path() {
  command -v Hyprland >/dev/null 2>&1 || command -v hyprland >/dev/null 2>&1
}

ubuntu_codename() {
  # Subshell so /etc/os-release vars do not leak into this script.
  if [[ ! -f /etc/os-release ]]; then
    return 0
  fi
  # shellcheck disable=SC1091
  ( . /etc/os-release && printf '%s' "${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}" )
}

try_apt_hyprland() {
  local pkgs=(hyprland xdg-desktop-portal-hyprland)
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would: sudo apt-get install -y ${pkgs[*]}"
    return 0
  fi
  if sudo apt-get install -y "${pkgs[@]}" 2>/dev/null; then
    return 0
  fi
  # Some archives ship only the compositor package.
  sudo apt-get install -y hyprland
}

add_hyprland_ppa() {
  local codename
  codename="$(ubuntu_codename)"
  if [[ -z "$codename" ]]; then
    log_err "Could not detect Ubuntu codename (UBUNTU_CODENAME). Aborting PPA add."
    return 1
  fi
  case "$codename" in
    noble|oracular|plucky|questing|resolute) ;;
    *)
      log_warn "Ubuntu codename '$codename' may not be published on ppa:cppiber/hyprland."
      log_warn "Continuing anyway; apt will fail clearly if the series is missing."
      ;;
  esac
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would: sudo add-apt-repository -y ppa:cppiber/hyprland"
    log_info "[dry-run] would: sudo apt-get update"
    return 0
  fi
  if ! command -v add-apt-repository >/dev/null 2>&1; then
    sudo apt-get install -y software-properties-common
  fi
  log_warn "Adding community PPA ppa:cppiber/hyprland (third-party; review before production use)."
  sudo add-apt-repository -y ppa:cppiber/hyprland
  sudo apt-get update
}

main() {
  log_info "Attempting Hyprland install (Mint/Ubuntu best-effort)"

  if hypr_on_path; then
    log_info "Hyprland already on PATH; nothing to install"
    return 0
  fi

  if [[ "$DRY_RUN" != "1" ]]; then
    sudo apt-get update
  else
    log_info "[dry-run] would: sudo apt-get update"
  fi

  # 1) Distro package (works on some Ubuntu releases with universe hyprland).
  log_info "Trying distro/universe hyprland package…"
  if try_apt_hyprland; then
    if [[ "$DRY_RUN" == "1" ]] || hypr_on_path; then
      log_info "Hyprland available via distro packages (or dry-run assumed success)"
      return 0
    fi
  fi

  # 2) Community PPA (Mint 22 / Ubuntu 24.04 noble and nearby series).
  log_info "Distro package missing or incomplete; trying ppa:cppiber/hyprland…"
  if ! add_hyprland_ppa; then
    log_err "Could not add Hyprland PPA"
    return 1
  fi
  if try_apt_hyprland; then
    if [[ "$DRY_RUN" == "1" ]] || hypr_on_path; then
      log_info "Hyprland installed via ppa:cppiber/hyprland"
      return 0
    fi
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] Hyprland install path finished (no packages actually installed)"
    return 0
  fi

  log_err "Hyprland still not on PATH after apt/PPA attempts."
  log_err "See docs/install-notes.md (build-from-source / Ubuntu-Hyprland script options)."
  return 1
}

main "$@"
