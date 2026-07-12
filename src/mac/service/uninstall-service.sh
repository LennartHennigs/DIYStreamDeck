#!/usr/bin/env bash
# uninstall-service.sh — remove the DIY StreamDeck watchdog LaunchAgent.

set -euo pipefail

LABEL="com.lennarthennigs.diystreamdeck"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true

if [ -f "$PLIST" ]; then
  rm "$PLIST"
  echo "Removed $PLIST"
else
  echo "No LaunchAgent plist found at $PLIST"
fi
echo "OK — the watchdog service is uninstalled."
