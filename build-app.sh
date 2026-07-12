#!/usr/bin/env bash
# Build DIYStreamDeck.app using PyInstaller.
# Requires pyinstaller in .venv: .venv/bin/pip install pyinstaller
#
# Usage:
#   ./build-app.sh             # build only
#   ./build-app.sh --install   # build + copy to /Applications/

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "${DIR}/.venv/bin/pyinstaller" ]; then
  echo "pyinstaller not found. Run: .venv/bin/pip install pyinstaller" >&2
  exit 1
fi

"${DIR}/.venv/bin/pyinstaller" "${DIR}/DIYStreamDeck.spec" --clean --noconfirm "$@"

echo ""
echo "Built: ${DIR}/dist/DIYStreamDeck.app"

if [ "${1:-}" = "--install" ]; then
  cp -r "${DIR}/dist/DIYStreamDeck.app" /Applications/
  echo "Installed: /Applications/DIYStreamDeck.app"
  echo "To add to Login Items: src/mac/service/install-service.sh --app"
fi
