# DIY Streamdeck claude plugin — traffic-light feedback for Claude Code hooks
# https://github.com/LennartHennigs/DIYStreamDeck
"""Claude plugin.

Listens on a Unix domain socket for one-word color messages ('green',
'red', 'yellow') and relays them to the Pico as `Claude: <color>` lines.
Intended for Claude Code lifecycle hooks — the shipped hook script writes
into the socket on `Stop`, `Notification`, and `StopFailure` events.

The name "claude" reflects what this plugin *does* rather than the LED
animation: the keypad becomes a persistent Claude Code status indicator
(the color the Pico sets stays lit until an app switch, rotation, or
keypress — see `src/pi_pico/code.py`).

Design notes:
- `SOCK_DGRAM` socket: many concurrent clients can send without contention.
- Background daemon thread drains the socket and calls send_to_keypad,
  which is the watchdog's `_send_line_to_keypad` — writes are serialized
  by the watchdog's existing `_serial_lock`, cooperating with heartbeats.
- Silent-drop on unknown payloads (junk from anything with write access
  to /tmp is ignored, matching the sounds plugin's input validation).
- Set `"listen_for_hooks": false` in claude.json to disable the socket
  listener; the keypad-triggerable claude.green/red/yellow commands
  still work in that mode.
"""

import os
import socket
import threading
from typing import Callable, Dict

from src.mac.plugins.base_plugin import BasePlugin


class ClaudePlugin(BasePlugin):
    """Relay incoming color datagrams to the Pico as `Claude: <color>` lines."""

    DEFAULT_SOCKET_PATH = "/tmp/streamdeck-claude.sock"
    VALID_COLORS = ("green", "red", "yellow")
    # Bound on recv buffer — color words are <=10 chars; anything larger is junk.
    _RECV_BUFSIZE = 64

    def __init__(self, config_file: str, verbose: bool = False) -> None:
        super().__init__(config_file, verbose)
        self.socket_path = self.config.get("socket_path", self.DEFAULT_SOCKET_PATH)
        # Opt-out: users who only want the keypad-triggerable test commands
        # can set "listen_for_hooks": false to skip binding the socket.
        self.listen_for_hooks = self.config.get("listen_for_hooks", True)
        self._send: Callable[[str], None] | None = None
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def commands(self) -> Dict[str, Callable]:
        # Keypad-triggerable test commands (round-trip is harmless).
        return {
            "claude.green": lambda: self._signal("green"),
            "claude.red": lambda: self._signal("red"),
            "claude.yellow": lambda: self._signal("yellow"),
        }

    def on_watchdog_start(self, send_to_keypad: Callable[[str], None]) -> None:
        self._send = send_to_keypad
        if not self.listen_for_hooks:
            self._log("claude: listen_for_hooks=false; socket listener disabled")
            return

        # Clean up any stale socket file from a previous crash.
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as e:
            self._log(f"claude: could not unlink stale socket {self.socket_path}: {e}")

        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self._sock.bind(self.socket_path)
        except OSError as e:
            print(f"claude: failed to bind socket {self.socket_path}: {e}")
            self._sock = None
            return

        self._thread = threading.Thread(
            target=self._listen_loop, name="claude-listener", daemon=True
        )
        self._thread.start()
        self._log(f"claude: listening on {self.socket_path}")

    def on_watchdog_stop(self) -> None:
        # Closing the socket unblocks recvfrom() with OSError, which the
        # listener loop treats as a shutdown signal. Single wakeup, no polling.
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError:
            pass

    # -- internals -------------------------------------------------------------

    def _listen_loop(self) -> None:
        sock = self._sock
        assert sock is not None
        while True:
            try:
                data, _addr = sock.recvfrom(self._RECV_BUFSIZE)
            except OSError:
                # Socket closed by on_watchdog_stop() — clean exit.
                return
            color = data.decode("utf-8", errors="ignore").strip().lower()
            if color in self.VALID_COLORS:
                self._signal(color)
            else:
                self._log(f"claude: dropped unknown payload {color!r}")

    def _signal(self, color: str) -> None:
        # Trust callers (commands() dict + validated _listen_loop); no
        # split-brain re-validation. Guard against being invoked before
        # on_watchdog_start() wires up the sender.
        if self._send is not None:
            self._send(f"Claude: {color}\n")
