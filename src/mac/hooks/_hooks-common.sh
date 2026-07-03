# Common prelude sourced by install-claude-hooks.sh and uninstall-claude-hooks.sh.
# Sets:
#   DIR            — directory of the calling script
#   HOOK_PATH      — absolute path to streamdeck-claude.py
#   SETTINGS_FILE  — ~/.claude/settings.json
#   BACKUP_FILE    — settings.json.bak
# Requires: jq (checked here). Validates existing settings.json is parseable
# JSON (if it exists) and creates a backup before any mutation.
#
# Callers should `set -euo pipefail` before sourcing.

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required. Install with: brew install jq" >&2
  exit 1
fi

# Resolve the hook path from the calling script's directory. This file lives
# next to install-*/uninstall-*.sh, so `DIR` reaches streamdeck-claude.py.
HOOK_PATH="${DIR}/streamdeck-claude.py"
SETTINGS_FILE="${HOME}/.claude/settings.json"
BACKUP_FILE="${SETTINGS_FILE}.bak"

# Validate JSON before touching. Missing file is fine (each script decides
# whether to create one or exit early).
if [ -f "$SETTINGS_FILE" ] && ! jq empty "$SETTINGS_FILE" >/dev/null 2>&1; then
  echo "Error: $SETTINGS_FILE is not valid JSON. Fix or delete it first." >&2
  exit 1
fi

# Backup the current file (if any). Callers should call this only when they
# intend to mutate the file.
backup_settings() {
  if [ -f "$SETTINGS_FILE" ]; then
    cp "$SETTINGS_FILE" "$BACKUP_FILE"
    echo "Backup: $BACKUP_FILE"
  fi
}

# Apply a jq patch and atomically replace SETTINGS_FILE. Usage:
#   apply_jq_patch '<jq program>' --arg cmd "$HOOK_PATH" ...
apply_jq_patch() {
  local program="$1"; shift
  local patched
  patched=$(jq "$@" "$program" "$SETTINGS_FILE")
  local tmp
  tmp="$(mktemp)"
  printf '%s\n' "$patched" > "$tmp"
  mv "$tmp" "$SETTINGS_FILE"
}
