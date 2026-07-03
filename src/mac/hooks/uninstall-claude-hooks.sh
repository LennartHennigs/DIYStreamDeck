#!/usr/bin/env bash
# uninstall-claude-hooks.sh — remove streamdeck-claude entries from Claude
# Code settings. Only touches entries whose command matches this repo's
# hook path. Peon-ping and other hooks are left untouched.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_hooks-common.sh
source "${DIR}/_hooks-common.sh"

if [ ! -f "$SETTINGS_FILE" ]; then
  echo "Nothing to do: $SETTINGS_FILE does not exist."
  exit 0
fi

backup_settings

# For each event, drop hook entries whose hooks[] contains our command.
apply_jq_patch '
  reduce ("Stop", "Notification", "StopFailure") as $evt (.;
    if (.hooks // {}) | has($evt) then
      .hooks[$evt] = (
        (.hooks[$evt] // [])
        | map(select(all(.hooks[]?; .command != $cmd)))
      )
    else
      .
    end
  )
' --arg cmd "$HOOK_PATH"

echo "OK — no streamdeck-claude entries remain in $SETTINGS_FILE."
