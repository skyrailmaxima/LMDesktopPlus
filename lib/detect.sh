detect_os() {
  OS_ID=unknown
  OS_LIKE=
  IS_MINT=0
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    source /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_LIKE="${ID_LIKE:-}"
    [[ "$OS_ID" == "linuxmint" ]] && IS_MINT=1
  fi
}

require_mint_or_warn() {
  detect_os
  if [[ "$IS_MINT" -eq 1 ]]; then return 0; fi
  if [[ "${FORCE:-0}" == "1" ]]; then
    log_warn "Not Linux Mint ($OS_ID); continuing because FORCE=1"
    return 0
  fi
  if [[ "$OS_ID" =~ (ubuntu|debian) || "$OS_LIKE" =~ (ubuntu|debian) ]]; then
    log_warn "Not Mint ($OS_ID) but Debian-family; continuing"
    return 0
  fi
  log_err "Unsupported OS: $OS_ID. Re-run with FORCE=1 to override."
  return 1
}
