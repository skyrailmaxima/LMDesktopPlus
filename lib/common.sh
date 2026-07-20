log_info() { printf '==> %s\n' "$*" >&2; }
log_warn() { printf '!!  %s\n' "$*" >&2; }
log_err()  { printf 'xx  %s\n' "$*" >&2; }

ensure_dir() { mkdir -p "$1"; }

# BACKUP_ROOT must be set by caller (timestamped).
backup_path() {
  local src="$1"
  [[ -e "$src" || -L "$src" ]] || return 0
  local rel="${src#"$HOME"/}"
  local dest="$BACKUP_ROOT/$rel"
  ensure_dir "$(dirname "$dest")"
  cp -a "$src" "$dest"
}

link_file() {
  local src="$1" dest="$2"
  ensure_dir "$(dirname "$dest")"
  if [[ -L "$dest" ]]; then
    local cur
    cur=$(readlink "$dest")
    [[ "$cur" == "$src" ]] && return 0
  fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    backup_path "$dest"
    rm -rf "$dest"
  fi
  ln -sfn "$src" "$dest"
}
