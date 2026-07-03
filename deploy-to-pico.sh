#!/bin/bash
# Deploy code.py and key_def.json to the Pi Pico CIRCUITPY volume.
# Usage: ./deploy-to-pico.sh [/Volumes/CIRCUITPY]
#
# The noasync remount prevents FAT32 corruption on macOS 14+ (async writes bug).
# This mount change is temporary — unplugging/replugging restores normal behaviour.

set -e

MOUNT="${1:-/Volumes/CIRCUITPY}"

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

DEVICE=$(df "$MOUNT" | awk 'NR==2 {print $1}')
remount_noasync "$DEVICE" "$MOUNT"

echo "Deploying to $MOUNT..."
cp -X src/pi_pico/code.py src/pi_pico/key_def.json "$MOUNT/"
sync

echo "Done. Pico will restart automatically."
