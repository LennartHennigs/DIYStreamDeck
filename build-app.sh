#!/usr/bin/env bash
# Build DIYStreamDeck.app using PyInstaller.
# Requires pyinstaller in .venv: .venv/bin/pip install pyinstaller
#
# Usage:
#   ./build-app.sh             # build only
#   ./build-app.sh --install   # build + copy to /Applications/

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ad-hoc sign a .app bundle. PyInstaller's internal signing fails on the bundled
# resources' extended attributes ("resource fork ... not allowed"), and even after
# clearing xattrs the first re-sign still leaves a resource fork that codesign
# --verify rejects; clearing xattrs and signing a *second* time (without touching
# _CodeSignature in between) yields a clean signature. Loop until --verify passes.
# Note: if the .app lives in an iCloud-synced folder (e.g. ~/Documents), the file
# provider re-stamps xattrs shortly after, invalidating the signature — the bundle
# still runs, but for a pristine signature keep/run it from a non-synced location
# such as /Applications.
sign_app() {
  local app="$1"
  local attempt
  for attempt in 1 2 3 4; do
    xattr -cr "${app}"
    codesign --force --deep --sign - "${app}" >/dev/null 2>&1 || true
    if codesign --verify --deep --strict "${app}" 2>/dev/null; then
      echo "Signed and verified ${app} (pass ${attempt})"
      return 0
    fi
  done
  echo "ERROR: could not produce a valid signature for ${app}" >&2
  return 1
}

if [ ! -f "${DIR}/.venv/bin/pyinstaller" ]; then
  echo "pyinstaller not found. Run: .venv/bin/pip install pyinstaller" >&2
  exit 1
fi

# Wipe previous artifacts. PyInstaller's --clean can leave a stale bootloader in
# build/ that trips "struct.error: unpack requires a buffer of 4 bytes" on the
# next run, so remove both dirs outright.
rm -rf "${DIR}/build" "${DIR}/dist"

"${DIR}/.venv/bin/pyinstaller" "${DIR}/DIYStreamDeck.spec" --clean --noconfirm "$@"

sign_app "${DIR}/dist/DIYStreamDeck.app"

echo ""
echo "Built: ${DIR}/dist/DIYStreamDeck.app"

if [ "${1:-}" = "--install" ]; then
  rm -rf /Applications/DIYStreamDeck.app
  cp -r "${DIR}/dist/DIYStreamDeck.app" /Applications/
  # Re-sign in place: /Applications isn't iCloud-synced, so this signature sticks
  # (and clears any xattrs the copy carried over from the synced build folder).
  sign_app /Applications/DIYStreamDeck.app
  echo "Installed: /Applications/DIYStreamDeck.app"
  echo "To add to Login Items: src/mac/service/install-service.sh --app"
fi
