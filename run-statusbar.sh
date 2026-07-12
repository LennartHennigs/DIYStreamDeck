#!/usr/bin/env bash
# Launcher for the DIY StreamDeck menu-bar app
# Usage: ./run-statusbar.sh [--port /dev/tty.usbmodemXXXX] [--verbose]

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_launcher-common.sh
source "${DIR}/_launcher-common.sh"

exec "${PYTHON_BIN}" -m src.mac.statusbar "$@"
