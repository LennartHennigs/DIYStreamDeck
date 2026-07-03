#!/usr/bin/env bash
# install-claude-hooks.sh — idempotently register the streamdeck-claude hook
# with Claude Code so lifecycle events (Stop, Notification, StopFailure)
# light the keypad green/red/yellow.
#
# Modifies ~/.claude/settings.json (creates a .bak first). Safe to re-run:
# already-installed entries are detected by matching the resolved hook path.
#
# Requires: jq (brew install jq).

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_hooks-common.sh
source "${DIR}/_hooks-common.sh"

if [ ! -f "$HOOK_PATH" ]; then
  echo "Error: hook script not found at $HOOK_PATH" >&2
  exit 1
fi

if [ ! -x "$HOOK_PATH" ]; then
  chmod +x "$HOOK_PATH"
fi

mkdir -p "${HOME}/.claude"
if [ ! -f "$SETTINGS_FILE" ]; then
  echo '{}' > "$SETTINGS_FILE"
fi

backup_settings

# For each target event, ensure exactly one entry exists whose
# hooks[].command == $HOOK_PATH. Skip if already present.
apply_jq_patch '
  .hooks = (.hooks // {}) |
  reduce ("Stop", "Notification", "StopFailure") as $evt (.;
    .hooks[$evt] = (.hooks[$evt] // []) |
    if any(.hooks[$evt][]?.hooks[]?; .command == $cmd) then
      .
    else
      .hooks[$evt] += [{
        matcher: "",
        hooks: [{
          type: "command",
          command: $cmd,
          timeout: 5,
          async: true
        }]
      }]
    end
  )
' --arg cmd "$HOOK_PATH"

echo "Hook path: $HOOK_PATH"
echo "OK — streamdeck-claude is registered for Stop, Notification, and StopFailure."
