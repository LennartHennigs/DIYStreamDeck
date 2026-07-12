#!/usr/bin/env bash
# install-service.sh — install the DIY StreamDeck watchdog as a user LaunchAgent
# so it starts at login and is kept alive by launchd.
#
# Usage:
#   ./install-service.sh              # headless watchdog (run-mac-watchdog.sh)
#   ./install-service.sh --statusbar  # menu-bar app (run-statusbar.sh)
#   ./install-service.sh --app        # bundled .app (/Applications/DIYStreamDeck.app)
#
# Safe to re-run: the agent is bootout'd and re-bootstrapped with the fresh plist.
# Logs: ~/Library/Logs/diystreamdeck.log

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${DIR}/../../.." && pwd)"
LABEL="com.lennarthennigs.diystreamdeck"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST="${PLIST_DIR}/${LABEL}.plist"

if [ "${1:-}" = "--app" ]; then
  APP_DIR="/Applications/DIYStreamDeck.app"
  LAUNCHER="${APP_DIR}/Contents/MacOS/DIYStreamDeck"
  TEMPLATE="${DIR}/${LABEL}.app.plist.template"
  mkdir -p "${HOME}/Library/Application Support/DIYStreamDeck"
  SED_EXTRA=(-e "s|__APP_BINARY__|${LAUNCHER}|g")
  MISSING_HINT="Build and install the app first: ./build-app.sh --install"
else
  LAUNCHER="${REPO_DIR}/run-mac-watchdog.sh"
  [ "${1:-}" = "--statusbar" ] && LAUNCHER="${REPO_DIR}/run-statusbar.sh"
  TEMPLATE="${DIR}/${LABEL}.plist.template"
  SED_EXTRA=(-e "s|__LAUNCHER__|${LAUNCHER}|g" -e "s|__REPO_DIR__|${REPO_DIR}|g")
  MISSING_HINT=""
fi

if [ ! -f "$TEMPLATE" ]; then
  echo "Error: plist template not found at $TEMPLATE" >&2
  exit 1
fi
if [ ! -x "$LAUNCHER" ]; then
  echo "Error: launcher not found or not executable: $LAUNCHER" >&2
  [ -n "$MISSING_HINT" ] && echo "$MISSING_HINT" >&2
  exit 1
fi

mkdir -p "$PLIST_DIR" "${HOME}/Library/Logs"
sed "${SED_EXTRA[@]}" -e "s|__HOME__|${HOME}|g" "$TEMPLATE" > "$PLIST"
echo "Launcher: $LAUNCHER"

# Reload if already installed (ignore errors when it wasn't loaded)
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Installed LaunchAgent: $PLIST"
echo "Logs: ${HOME}/Library/Logs/diystreamdeck.log"
echo "OK — the watchdog will start at login and stay running."
