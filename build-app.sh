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

# Split our own flags from pass-through PyInstaller args. --install must NOT be
# forwarded to PyInstaller (it rejects unknown options); anything else is passed
# through so callers can add extra PyInstaller flags.
INSTALL=0
PYI_ARGS=()
for arg in "$@"; do
  if [ "${arg}" = "--install" ]; then
    INSTALL=1
  else
    PYI_ARGS+=("${arg}")
  fi
done

# Wipe previous artifacts. PyInstaller's --clean can leave a stale bootloader in
# build/ that trips "struct.error: unpack requires a buffer of 4 bytes" on the
# next run, so remove both dirs outright. Under an iCloud-synced folder (e.g.
# ~/Documents) the file provider re-materializes files mid-delete, so a single
# `rm -rf` can fail with "Directory not empty" — retry a few times.
rm_retry() {
  local target="$1" attempt
  for attempt in 1 2 3 4 5; do
    rm -rf "${target}" 2>/dev/null
    [ ! -e "${target}" ] && return 0
    sleep 1
  done
  rm -rf "${target}"  # final attempt, let any real error surface
}
rm_retry "${DIR}/build"
rm_retry "${DIR}/dist"

"${DIR}/.venv/bin/pyinstaller" "${DIR}/DIYStreamDeck.spec" --clean --noconfirm \
  ${PYI_ARGS[@]+"${PYI_ARGS[@]}"}

# Best-effort sign in place. Under an iCloud-synced repo (~/Documents) the file
# provider re-stamps xattrs and can lose codesign the --verify race on every
# pass — the app still runs (ad-hoc signed), so warn rather than abort. For a
# pristine signature use --install (re-signs the non-synced /Applications copy).
if ! sign_app "${DIR}/dist/DIYStreamDeck.app"; then
  echo "WARNING: dist app not cleanly signed (expected under iCloud-synced ~/Documents)." >&2
  echo "         The app still runs; use --install for a pristine /Applications signature." >&2
fi

echo ""
echo "Built: ${DIR}/dist/DIYStreamDeck.app"

if [ "${INSTALL}" = "1" ]; then
  rm -rf /Applications/DIYStreamDeck.app
  cp -r "${DIR}/dist/DIYStreamDeck.app" /Applications/
  # Re-sign in place: /Applications isn't iCloud-synced, so xattr churn isn't a
  # factor here. Best-effort: PyInstaller's bundled Python.framework has an
  # "ambiguous bundle format" that codesign --deep --strict rejects regardless,
  # so warn rather than abort — the ad-hoc-signed app still launches locally.
  if ! sign_app /Applications/DIYStreamDeck.app; then
    echo "WARNING: /Applications app not cleanly signed (PyInstaller Python.framework" >&2
    echo "         layout defeats codesign --deep --strict). It still runs locally." >&2
  fi
  echo "Installed: /Applications/DIYStreamDeck.app"
  echo "To add to Login Items: src/mac/service/install-service.sh --app"
fi
