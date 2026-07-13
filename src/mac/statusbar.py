# DIY Streamdeck menu-bar app for a Mac
# https://github.com/LennartHennigs/DIYStreamDeck
"""Minimal menu-bar wrapper around the watchdog.

Shows connection state in the status bar, a cheat sheet of the active app's
key layout (from key_def.json), and an Auto-connect toggle. The session
protocol (handshake, heartbeat, plugin lifecycle) lives in src.mac.watchdog's
start_session/end_session — this file is only UI and reconnect policy.

Run with ./run-statusbar.sh, or install as a LaunchAgent via
src/mac/service/install-service.sh --statusbar.
"""
import argparse
import os
import sys
import tempfile
import webbrowser

import rumps

from src.mac import config_paths, github_update, pico_deploy
from src.mac.layout_formatter import load_key_def, layout_lines
from src.mac.watchdog import (
    VERSION,
    _attempt_connect,
    end_session,
    load_plugins,
    start_session,
)

# In a PyInstaller bundle this file is the entry script, so __file__ points at
# the bundle root (Contents/Frameworks) instead of src/mac. The datas keep the
# src/mac/... layout under sys._MEIPASS, so resolve resources from there.
if getattr(sys, 'frozen', False):
    _MAC_DIR = os.path.join(sys._MEIPASS, 'src', 'mac')
else:
    _MAC_DIR = os.path.dirname(os.path.abspath(__file__))
# key_def.json lives in the user config folder (~/Documents/DIYStreamDeck),
# seeded from the bundle on first run — see config_paths.ensure_config_dir().
DEFAULT_KEY_DEF = config_paths.key_def_path()
_GRID_ICON = os.path.join(_MAC_DIR, 'assets', 'grid_icon.png')

TICK_SECONDS = 0.1
RETRY_TICKS = 20        # first (re)connect attempt after ~2 s
MAX_RETRY_TICKS = 150   # back off to ~15 s, mirroring _connect_or_wait


class StreamDeckApp(rumps.App):

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("DIY StreamDeck", title=" ", icon=_GRID_ICON, template=True, quit_button=None)
        self.args = args
        self.plugins = load_plugins(verbose=args.verbose)

        self._watchdog = None
        self._heartbeat_thread = None
        self._retry_ticks = RETRY_TICKS
        self._retry_countdown = 0

        self._status_item = rumps.MenuItem("◌  Starting...")
        self._layout_menu = rumps.MenuItem("Layout")
        self._layout_menu.add(rumps.MenuItem("(no app yet)"))
        self._autoconnect_item = rumps.MenuItem("Auto-connect", callback=self._toggle_autoconnect)
        self._autoconnect_item.state = 1
        self._connect_item = rumps.MenuItem("Connect now", callback=self._connect_now)
        self.menu = [
            self._status_item,
            self._layout_menu,
            None,
            self._autoconnect_item,
            self._connect_item,
            None,
            rumps.MenuItem("Reload layout on Pico", callback=self._reload_layout),
            rumps.MenuItem("Update firmware from GitHub", callback=self._update_firmware),
            None,
            rumps.MenuItem("Project on GitHub", callback=self._open_github),
            None,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

        self._timer = rumps.Timer(self._tick, TICK_SECONDS)
        self._timer.start()

    # -- connection state machine (runs on the main thread via rumps.Timer) ----

    def _tick(self, _timer) -> None:
        if self._watchdog is not None:
            self._watchdog.check_serial()
            if self._watchdog._disconnected.is_set():
                self._teardown_session(send_bye=False)
                self._enter_disconnected_state()
            return
        if self._autoconnect_item.state:
            self._retry_countdown -= 1
            if self._retry_countdown <= 0:
                if not self._try_connect():
                    # capped backoff — don't walk the USB registry every 2 s forever
                    self._retry_ticks = min(int(self._retry_ticks * 1.5), MAX_RETRY_TICKS)
                self._retry_countdown = self._retry_ticks

    def _enter_disconnected_state(self) -> None:
        self._retry_ticks = RETRY_TICKS
        self._retry_countdown = 0  # retry on the next tick
        if self._autoconnect_item.state:
            self._set_status("◌  Searching for Pico...")
        else:
            self._set_status("○  Disconnected")

    def _try_connect(self) -> bool:
        ser = _attempt_connect(self.args)
        if ser is None:
            return False
        self._watchdog, self._heartbeat_thread = start_session(
            ser, self.args, self.plugins, on_app_changed=self._on_app_changed)
        self._retry_ticks = RETRY_TICKS
        self._set_status(f"●  Connected: {ser.port}")
        if self.args.verbose:
            print(f"Connected: {ser.port}")
        return True

    def _teardown_session(self, send_bye: bool = False) -> None:
        if self._watchdog is None:
            return
        end_session(self._watchdog, self._heartbeat_thread, self.plugins,
                    send_bye=send_bye)
        self._watchdog = None
        self._heartbeat_thread = None

    # -- cheat sheet ------------------------------------------------------------

    def _on_app_changed(self, app_name: str) -> None:
        try:
            key_def = load_key_def(self.args.key_def)
            lines = layout_lines(key_def, app_name.split(" (", 1)[0])
        except (OSError, ValueError) as e:
            lines = [f"key_def.json error: {e}"]
        if getattr(self, '_last_app_name', None) == app_name and \
                getattr(self, '_last_layout_lines', None) == lines:
            return
        self._last_app_name = app_name
        self._last_layout_lines = lines
        # rumps MenuItem has no public clear-children API on all versions;
        # rebuild via the underlying dict interface it exposes.
        for key in list(self._layout_menu.keys()):
            del self._layout_menu[key]
        self._layout_menu.add(rumps.MenuItem(app_name))
        for line in lines or ["(no keys defined)"]:
            self._layout_menu.add(rumps.MenuItem(line))

    # -- menu callbacks -----------------------------------------------------------

    def _set_status(self, text: str) -> None:
        self._status_item.title = text

    def _toggle_autoconnect(self, item: rumps.MenuItem) -> None:
        item.state = not item.state
        if self._watchdog is None:
            self._enter_disconnected_state()

    def _connect_now(self, _item) -> None:
        self._retry_ticks = RETRY_TICKS
        if self._watchdog is None and not self._try_connect():
            self._set_status("○  Pico not found")

    # -- Pico deploy / firmware -------------------------------------------------

    def _force_reconnect(self) -> None:
        """Drop the session so the state machine reconnects + re-HELLOs, which
        repaints the layout after the Pico auto-reloads."""
        if self._watchdog is not None:
            self._teardown_session(send_bye=False)
        self._enter_disconnected_state()

    def _reload_layout(self, _item) -> None:
        if pico_deploy.circuitpy_mount() is None:
            self._set_status("○  Pico storage not mounted")
            return
        try:
            pico_deploy.push_key_def()
        except pico_deploy.PicoDeployError as e:
            self._set_status(f"○  {e}")
            return
        self._set_status("◌  Reloading layout...")
        self._force_reconnect()

    def _update_firmware(self, _item) -> None:
        if pico_deploy.circuitpy_mount() is None:
            self._set_status("○  Pico storage not mounted")
            return
        try:
            ref, code_py = github_update.latest_code_py()
        except github_update.UpdateError:
            self._set_status("○  Update failed (offline?)")
            return
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as tmp:
                tmp.write(code_py)
                tmp_path = tmp.name
            pico_deploy.push_file(tmp_path, 'code.py')
        except pico_deploy.PicoDeployError as e:
            self._set_status(f"○  {e}")
            return
        finally:
            try:
                os.unlink(tmp_path)
            except (OSError, NameError):
                pass
        self._set_status(f"◌  Installed firmware {ref}...")
        self._force_reconnect()

    def _open_github(self, _item) -> None:
        webbrowser.open(github_update.REPO_URL)

    def _quit(self, _item) -> None:
        self._timer.stop()
        self._teardown_session(send_bye=True)
        rumps.quit_application()


def main() -> None:
    parser = argparse.ArgumentParser(description='DIY StreamDeck menu-bar app')
    parser.add_argument('--port', default=None,
                        help='Serial port for the microcontroller (auto-detected if omitted)')
    parser.add_argument('--speed', type=int, default=9600,
                        help='Baud rate for the serial connection (default: 9600)')
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='Log activity to stdout')
    parser.add_argument('--rotate', choices=['CW', 'CCW'],
                        help='Rotation direction for the keypad (default: none)')
    parser.add_argument('--key-def', default=DEFAULT_KEY_DEF,
                        help='Path to key_def.json for the layout cheat sheet')
    args = parser.parse_args()

    print(f'DIY StreamDeck menu-bar app {VERSION}')
    config_paths.ensure_config_dir()  # create + seed ~/Documents/DIYStreamDeck
    StreamDeckApp(args).run()


if __name__ == "__main__":
    main()
