#!/bin/bash
# Deploy code.py and/or key_def.json to the Pi Pico CIRCUITPY volume.
# Usage: ./deploy-to-pico.sh [--code|--keys] [/Volumes/CIRCUITPY]
#
#   --code   deploy only code.py (firmware)
#   --keys   deploy only key_def.json (key settings)
#   (default: deploy both)
#
# The noasync remount prevents FAT32 corruption on macOS 14+ (async writes bug).
# This mount change is temporary — unplugging/replugging restores normal behaviour.

set -e

usage() {
  echo "Usage: ./deploy-to-pico.sh [--code|--keys] [/Volumes/CIRCUITPY]"
  echo "  --code   deploy only code.py (firmware)"
  echo "  --keys   deploy only key_def.json (key settings)"
  echo "  (default: deploy both)"
}

MOUNT="/Volumes/CIRCUITPY"
DEPLOY_CODE=true
DEPLOY_KEYS=true

for arg in "$@"; do
  case "$arg" in
    --code) DEPLOY_CODE=true; DEPLOY_KEYS=false ;;
    --keys) DEPLOY_CODE=false; DEPLOY_KEYS=true ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Error: unknown option '$arg'"; usage; exit 1 ;;
    *) MOUNT="$arg" ;;
  esac
done

if [ ! -d "$MOUNT" ]; then
  echo "Error: CIRCUITPY not found at $MOUNT"
  echo "Make sure the Pico is connected and mounted."
  exit 1
fi

remount_noasync() {
  local device="$1" mount="$2"
  echo "Remounting $device at $mount with noasync..."
  sudo umount "$mount"
  local i=0
  until sudo mount -o noasync -t msdos "$device" "$mount" 2>/dev/null; do
    i=$((i + 1))
    [ $i -ge 5 ] && { echo "Error: remount failed after 5 attempts"; exit 1; }
    sleep 0.5
  done
}

# key_def.json single source of truth: the user config folder
# (~/Documents/DIYStreamDeck, override with STREAMDECK_CONFIG_DIR) if it exists,
# else the in-repo copy.
CONFIG_DIR="${STREAMDECK_CONFIG_DIR:-$HOME/Documents/DIYStreamDeck}"
KEY_DEF_SRC="src/pi_pico/key_def.json"
[ -f "$CONFIG_DIR/key_def.json" ] && KEY_DEF_SRC="$CONFIG_DIR/key_def.json"

DEVICE=$(df "$MOUNT" | awk 'NR==2 {print $1}')
remount_noasync "$DEVICE" "$MOUNT"

echo "Deploying to $MOUNT..."
$DEPLOY_CODE && { echo "  code.py"; cp -X src/pi_pico/code.py "$MOUNT/"; }
$DEPLOY_KEYS && { echo "  key_def.json (from $KEY_DEF_SRC)"; cp -X "$KEY_DEF_SRC" "$MOUNT/key_def.json"; }
sync

echo "Done. Pico will restart automatically."
