#!/usr/bin/env python3
"""Claude Code hook — relays lifecycle events to the DIY StreamDeck keypad.

Fired by Claude Code on Stop / Notification / StopFailure events.
Reads the event JSON payload on stdin, decides a color, writes a single
UDP datagram to the claude plugin's Unix socket. Silent on any failure —
if the watchdog / claude plugin isn't running, Claude Code proceeds
unaffected.

Register from `~/.claude/settings.json` (or install with
`install-claude-hooks.sh`).
"""
import json
import os
import socket
import sys

DEFAULT_SOCKET_PATH = "/tmp/streamdeck-claude.sock"

EVENT_TO_COLOR = {
    "Stop": "green",
    "Notification": "red",
    "StopFailure": "yellow",
}


def main() -> None:
    socket_path = os.environ.get("STREAMDECK_CLAUDE_SOCKET", DEFAULT_SOCKET_PATH)

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # bad payload; stay silent

    if not isinstance(payload, dict):
        return
    event = payload.get("hook_event_name")
    color = EVENT_TO_COLOR.get(event)
    if not color:
        return

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        try:
            s.sendto(color.encode("utf-8"), socket_path)
        finally:
            s.close()
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        # Watchdog / claude plugin not running, or socket vanished mid-send.
        # Claude Code should not slow down when the keypad isn't there.
        pass


if __name__ == "__main__":
    main()
