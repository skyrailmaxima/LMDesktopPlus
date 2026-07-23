#!/usr/bin/env bash
# Best-effort Hyprland install for Linux Mint / Ubuntu-family hosts.
# Does NOT replace Cinnamon; only installs the compositor + portal so
# LMDesktopPlus can register a Wayland session afterward.
#
# Community PPA (ppa:cppiber/hyprland) is NEVER added unless explicitly
# opted in via --allow-community-ppa or --hyprland-source=ppa.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/lib/common.sh"

DRY_RUN="${DRY_RUN:-0}"
ALLOW_COMMUNITY_PPA="${ALLOW_COMMUNITY_PPA:-0}"
# distro | ppa | existing
HYPRLAND_SOURCE="${HYPRLAND_SOURCE:-distro}"

usage() {
  cat <<'EOF'
Usage: install-hyprland-mint.sh [--allow-community-ppa]
                                [--hyprland-source=distro|ppa|existing]

  --allow-community-ppa
      After distro packages fail, add ppa:cppiber/hyprland and retry.
  --hyprland-source=distro
      Only try official/universe apt packages (default).
  --hyprland-source=ppa
      Allow the community PPA (implies --allow-community-ppa).
  --hyprland-source=existing
      Require Hyprland already on PATH; do not install packages.

Env: DRY_RUN=1, ALLOW_COMMUNITY_PPA=1, HYPRLAND_SOURCE=...
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-community-ppa) ALLOW_COMMUNITY_PPA=1 ;;
    --hyprland-source=distro) HYPRLAND_SOURCE=distro ;;
    --hyprland-source=ppa) HYPRLAND_SOURCE=ppa; ALLOW_COMMUNITY_PPA=1 ;;
    --hyprland-source=existing) HYPRLAND_SOURCE=existing ;;
    --hyprland-source=*)
      log_err "Unknown hyprland source: ${1#*=} (use distro|ppa|existing)"
      exit 1
      ;;
    -h|--help) usage; exit 0 ;;
    *) log_err "Unknown flag: $1"; usage; exit 1 ;;
  esac
  shift
done

hypr_on_path() {
  command -v Hyprland >/dev/null 2>&1 || command -v hyprland >/dev/null 2>&1
}

ubuntu_codename() {
  if [[ ! -f /etc/os-release ]]; then
    return 0
  fi
  # shellcheck disable=SC1091
  ( . /etc/os-release && printf '%s' "${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}" )
}

print_manual_options() {
  log_err "Hyprland is not available via the selected install source."
  log_info "Manual options:"
  log_info "  1) Re-run with an explicit community PPA opt-in:"
  log_info "       ./install.sh --with-hyprland --allow-community-ppa"
  log_info "       # or: --hyprland-source=ppa"
  log_info "  2) Install Hyprland yourself, then re-run ./install.sh"
  log_info "  3) See docs/install-notes.md for build-from-source guidance"
}

try_apt_hyprland() {
  local pkgs=(hyprland xdg-desktop-portal-hyprland)
  local output=""
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would: sudo apt-get install -y ${pkgs[*]}"
    return 0
  fi
  if output="$(sudo apt-get install -y "${pkgs[@]}" 2>&1)"; then
    printf '%s\n' "$output"
    return 0
  fi
  log_warn "Combined Hyprland package installation failed:"
  printf '%s\n' "$output" >&2
  log_info "Retrying compositor package without the portal."
  if output="$(sudo apt-get install -y hyprland 2>&1)"; then
    printf '%s\n' "$output"
    return 0
  fi
  log_warn "Compositor-only package installation failed:"
  printf '%s\n' "$output" >&2
  return 1
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
    local output=""
    if ! output="$(sudo apt-get install -y software-properties-common 2>&1)"; then
      log_err "Failed to install software-properties-common:"
      printf '%s\n' "$output" >&2
      return 1
    fi
  fi
  log_warn "Adding community PPA ppa:cppiber/hyprland (third-party; review before production use)."
  sudo add-apt-repository -y ppa:cppiber/hyprland
  sudo apt-get update
}

main() {
  log_info "Attempting Hyprland install (source=$HYPRLAND_SOURCE, community_ppa=$ALLOW_COMMUNITY_PPA)"

  if hypr_on_path; then
    log_info "Hyprland already on PATH; nothing to install"
    return 0
  fi

  if [[ "$HYPRLAND_SOURCE" == "existing" ]]; then
    log_err "Hyprland not on PATH and --hyprland-source=existing was requested."
    print_manual_options
    return 1
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would: sudo apt-get update"
    if [[ "$HYPRLAND_SOURCE" != "ppa" ]]; then
      log_info "[dry-run] would try distro/universe packages: hyprland xdg-desktop-portal-hyprland"
    fi
    if [[ "$ALLOW_COMMUNITY_PPA" == "1" || "$HYPRLAND_SOURCE" == "ppa" ]]; then
      log_info "[dry-run] if distro packages fail, would: sudo add-apt-repository -y ppa:cppiber/hyprland"
      log_info "[dry-run] would: sudo apt-get update && retry hyprland packages"
    else
      log_info "[dry-run] community PPA would NOT be added (pass --allow-community-ppa to opt in)"
    fi
    return 0
  fi

  sudo apt-get update

  if [[ "$HYPRLAND_SOURCE" != "ppa" ]]; then
    log_info "Trying distro/universe hyprland package…"
    if try_apt_hyprland && hypr_on_path; then
      log_info "Hyprland available via distro packages"
      return 0
    fi
  fi

  if [[ "$ALLOW_COMMUNITY_PPA" == "1" || "$HYPRLAND_SOURCE" == "ppa" ]]; then
    log_info "Distro package missing or incomplete; community PPA explicitly allowed…"
    if ! add_hyprland_ppa; then
      log_err "Could not add Hyprland PPA"
      print_manual_options
      return 1
    fi
    if try_apt_hyprland && hypr_on_path; then
      log_info "Hyprland installed via ppa:cppiber/hyprland"
      return 0
    fi
  else
    log_warn "Distro packages did not provide Hyprland; community PPA was NOT added."
    log_warn "Re-run with --allow-community-ppa (or --hyprland-source=ppa) to opt in."
  fi

  print_manual_options
  return 1
}

main "$@"
