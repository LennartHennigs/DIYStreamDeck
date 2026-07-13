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

# Wipe previous artifacts. PyInstaller's --clean can leave a stale bootloader in
# build/ that trips "struct.error: unpack requires a buffer of 4 bytes" on the
# next run, so remove both dirs outright.
rm -rf "${DIR}/build" "${DIR}/dist"

"${DIR}/.venv/bin/pyinstaller" "${DIR}/DIYStreamDeck.spec" --clean --noconfirm "$@"

# PyInstaller's internal ad-hoc signing fails on the bundled resources' extended
# attributes ("resource fork ... not allowed"). Even after clearing xattrs, the first
# re-sign still leaves a resource fork that `codesign --verify` rejects; clearing xattrs
# and signing a *second* time (without touching _CodeSignature in between) yields a clean
# signature. Loop xattr-clear + re-sign until --verify passes.
APP="${DIR}/dist/DIYStreamDeck.app"
for attempt in 1 2 3 4; do
  xattr -cr "${APP}"
  codesign --force --deep --sign - "${APP}" >/dev/null 2>&1 || true
  if codesign --verify --deep --strict "${APP}" 2>/dev/null; then
    echo "Signed and verified .app (pass ${attempt})"
    break
  fi
  [ "${attempt}" = 4 ] && { echo "ERROR: could not produce a valid signature" >&2; exit 1; }
done

echo ""
echo "Built: ${DIR}/dist/DIYStreamDeck.app"

if [ "${1:-}" = "--install" ]; then
  cp -r "${DIR}/dist/DIYStreamDeck.app" /Applications/
  echo "Installed: /Applications/DIYStreamDeck.app"
  echo "To add to Login Items: src/mac/service/install-service.sh --app"
fi
