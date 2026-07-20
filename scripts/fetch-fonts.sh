#!/usr/bin/env bash
# Fetches display fonts (DotGothic16, Zen Dots) used by the vapor//matrix
# theme into ~/.local/share/fonts/lmdesktopplus/. Network failures are
# non-fatal: each font is skipped with a warning so install.sh can proceed
# offline (JetBrains Mono ships via apt and is not handled here).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=/dev/null
if [[ -f "$ROOT/lib/common.sh" ]]; then
  source "$ROOT/lib/common.sh"
else
  log_info() { printf '==> %s\n' "$*" >&2; }
  log_warn() { printf '!!  %s\n' "$*" >&2; }
  log_err()  { printf 'xx  %s\n' "$*" >&2; }
fi

FONT_DIR="${FONT_DIR:-$HOME/.local/share/fonts/lmdesktopplus}"
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"
TIMEOUT="${FETCH_TIMEOUT:-10}"

# name|filename|url (Google Fonts OFL sources, mirrored from google/fonts on GitHub)
FONTS=(
  "DotGothic16|DotGothic16-Regular.ttf|https://github.com/google/fonts/raw/main/ofl/dotgothic16/DotGothic16-Regular.ttf"
  "Zen Dots|ZenDots-Regular.ttf|https://github.com/google/fonts/raw/main/ofl/zendots/ZenDots-Regular.ttf"
)

fetch_one() {
  local url="$1" dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --location --connect-timeout "$TIMEOUT" --max-time $((TIMEOUT * 3)) --output "$dest" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --quiet --timeout="$TIMEOUT" --tries=1 --output-document="$dest" "$url"
  else
    return 127
  fi
}

main() {
  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    log_warn "Neither curl nor wget found; skipping font fetch"
    return 0
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    local names=() entry
    for entry in "${FONTS[@]}"; do
      names+=("${entry%%|*}")
    done
    log_info "DRY_RUN font fetch into $FONT_DIR: ${names[*]}"
    return 0
  fi

  mkdir -p "$FONT_DIR"

  local installed=0 skipped=0
  local entry name file url dest
  for entry in "${FONTS[@]}"; do
    name="${entry%%|*}"
    file="${entry#*|}"; file="${file%%|*}"
    url="${entry##*|}"
    dest="$FONT_DIR/$file"

    if [[ -f "$dest" && "$FORCE" != "1" ]]; then
      log_info "$name already present at $dest (skip; FORCE=1 to refetch)"
      installed=$((installed + 1))
      continue
    fi

    log_info "Fetching $name..."
    local tmp="$dest.part"
    if fetch_one "$url" "$tmp" && [[ -s "$tmp" ]]; then
      mv "$tmp" "$dest"
      log_info "Installed $name -> $dest"
      installed=$((installed + 1))
    else
      rm -f "$tmp"
      log_warn "Could not fetch $name (offline or unreachable); skipping"
      skipped=$((skipped + 1))
    fi
  done

  if [[ "$installed" -gt 0 ]]; then
    if command -v fc-cache >/dev/null 2>&1; then
      fc-cache -f "$FONT_DIR" >/dev/null 2>&1 || log_warn "fc-cache failed; fonts installed but cache not refreshed"
    else
      log_warn "fc-cache not found; skipping font cache refresh"
    fi
  fi

  log_info "Font fetch done: $installed installed/cached, $skipped skipped"
  return 0
}

main "$@"
