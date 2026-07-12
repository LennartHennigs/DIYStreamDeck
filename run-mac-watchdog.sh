#!/usr/bin/env bash
# Simple launcher for the mac watchdog script
# Usage: ./run-mac-watchdog.sh --port /dev/tty.usbmodemXXXX [--speed 9600] [--verbose]

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_launcher-common.sh
source "${DIR}/_launcher-common.sh"

exec "${PYTHON_BIN}" -m src.mac.watchdog "$@"
