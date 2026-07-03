#!/usr/bin/env bash
# test-claude.sh — send Claude Code status colors to the running watchdog
# so you can verify the keypad signal chain (socket → plugin → serial → Pico)
# without waiting for a real Claude Code event.
#
# The color the Pico sets stays lit until an app switch, rotation, keypress,
# or the next color — see src/pi_pico/code.py.
#
# Usage:
#   ./test-claude.sh                     # cycle green → red → yellow
#   ./test-claude.sh green               # one color
#   ./test-claude.sh red yellow green    # any sequence you like
#   ./test-claude.sh --interval 1 all    # slow it down to 1s between colors
#
# Prerequisites:
#   • The watchdog is running (`./run-mac-watchdog.sh`) so the claude plugin
#     is listening on /tmp/streamdeck-claude.sock.
#   • The Pico is connected and the current `code.py` (with the Claude:
#     handler) is deployed.
#
# Exits 1 if the socket doesn't exist (watchdog not running) so you don't
# stare at a dark keypad wondering why.

set -euo pipefail

SOCKET="${STREAMDECK_CLAUDE_SOCKET:-/tmp/streamdeck-claude.sock}"
INTERVAL="0.8"

usage() {
  sed -n '2,22p' "$0"
  exit "${1:-0}"
}

# Parse args
COLORS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage 0 ;;
    -i|--interval) INTERVAL="$2"; shift 2 ;;
    all) COLORS+=(green red yellow); shift ;;
    green|red|yellow) COLORS+=("$1"); shift ;;
    *) echo "Unknown argument: $1" >&2; usage 1 ;;
  esac
done

# Default cycle if nothing given
if [ ${#COLORS[@]} -eq 0 ]; then
  COLORS=(green red yellow)
fi

# Sanity: watchdog must be up
if [ ! -S "$SOCKET" ]; then
  echo "Error: socket $SOCKET does not exist." >&2
  echo "Start the watchdog first: ./run-mac-watchdog.sh --verbose" >&2
  exit 1
fi

# Pick a sender: prefer `nc -U` (built-in on macOS); fall back to a tiny
# Python one-liner if nc is missing or the -U variant isn't available.
send() {
  local color="$1"
  if command -v nc >/dev/null 2>&1 && printf "%s" "$color" | nc -U -w 1 "$SOCKET" 2>/dev/null; then
    return 0
  fi
  python3 -c "
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
s.settimeout(1)
s.sendto(sys.argv[1].encode(), sys.argv[2])
s.close()
" "$color" "$SOCKET"
}

for color in "${COLORS[@]}"; do
  echo "→ $color"
  send "$color"
  sleep "$INTERVAL"
done

echo "Done. If the keypad didn't light up, check:"
echo "  • Pico is connected and running the current code.py (with Claude: handler)"
echo "  • Watchdog console shows: claude: listening on $SOCKET"
