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
import webbrowser

import rumps
from AppKit import NSColor, NSForegroundColorAttributeName
from Foundation import NSMutableAttributedString

from src.mac import config_paths, github_update, login_item
from src.mac.layout_formatter import layout_entries, load_key_def
from src.mac.watchdog import (
    VERSION,
    _attempt_connect,
    end_session,
    load_plugins,
    start_session,
)

# Status-dot colors (r, g, b). Dark green for connected; the rest track state.
_GREEN = (0, 128, 0)
_GREY = (140, 140, 140)
_AMBER = (200, 150, 0)
_RED = (200, 60, 60)


def _set_dot_title(item: 'rumps.MenuItem', rgb, text: str) -> None:
    """Render '●  text' on a menu item with only the ● glyph colored rgb.

    rumps has no colored-text API, so we set an NSAttributedString directly on
    the underlying NSMenuItem. If rgb is None, no dot is shown (plain text).

    item.title is always set to `text` first so rumps' menu keeps a stable,
    unique key for the item; the attributed title only overrides the display."""
    item.title = text
    if rgb is None:
        item._menuitem.setAttributedTitle_(None)
        return
    attr = NSMutableAttributedString.alloc().initWithString_(f"●  {text}")
    color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
        rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0)
    attr.addAttribute_value_range_(NSForegroundColorAttributeName, color, (0, 1))
    item._menuitem.setAttributedTitle_(attr)

# In a PyInstaller bundle this file is the entry script, so __file__ points at
# the bundle root instead of src/mac; config_paths.bundle_root() resolves the
# frozen-aware root the datas keep the src/mac/... layout under.
_MAC_DIR = os.path.join(config_paths.bundle_root(), 'src', 'mac')
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

        self._status_item = rumps.MenuItem("Starting...")
        self._set_status("Starting...", _GREY)
        self._layout_menu = rumps.MenuItem("Layout")
        self._layout_menu.add(rumps.MenuItem("(no app yet)"))
        self._autoconnect_item = rumps.MenuItem("Auto-connect", callback=self._toggle_autoconnect)
        self._autoconnect_item.state = 1
        self._connect_item = rumps.MenuItem("Connect now", callback=self._connect_now)
        self._login_item = rumps.MenuItem("Start at login", callback=self._toggle_login_item)
        self._login_item.state = login_item.is_enabled()
        self.menu = [
            self._status_item,
            self._layout_menu,
            None,
            self._autoconnect_item,
            self._connect_item,
            self._login_item,
            None,
            rumps.MenuItem("Open Project on GitHub", callback=self._open_github),
            rumps.MenuItem("About DIY StreamDeck…", callback=self._about),
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
            self._set_status("Searching for Pico...", _AMBER)
        else:
            self._set_status("Disconnected", _GREY)

    def _try_connect(self) -> bool:
        ser = _attempt_connect(self.args)
        if ser is None:
            return False
        self._watchdog, self._heartbeat_thread = start_session(
            ser, self.args, self.plugins, on_app_changed=self._on_app_changed)
        self._retry_ticks = RETRY_TICKS
        self._set_status(f"Connected ({ser.port})", _GREEN)
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
            entries = layout_entries(key_def, app_name.split(" (", 1)[0])
        except (OSError, ValueError) as e:
            entries = None
            err = f"key_def.json error: {e}"
        if getattr(self, '_last_app_name', None) == app_name and \
                getattr(self, '_last_layout_entries', None) == entries:
            return
        self._last_app_name = app_name
        self._last_layout_entries = entries
        # rumps MenuItem has no public clear-children API on all versions;
        # rebuild via the underlying dict interface it exposes.
        for key in list(self._layout_menu.keys()):
            del self._layout_menu[key]
        self._layout_menu.add(rumps.MenuItem(app_name))
        if entries is None:
            self._layout_menu.add(rumps.MenuItem(err))
            return
        if not entries:
            self._layout_menu.add(rumps.MenuItem("(no keys defined)"))
            return
        for num, text, rgb in entries:
            item = rumps.MenuItem("")
            _set_dot_title(item, rgb, f"Key {num:2d} — {text}")
            self._layout_menu.add(item)

    # -- menu callbacks -----------------------------------------------------------

    def _set_status(self, text: str, rgb=_GREY) -> None:
        _set_dot_title(self._status_item, rgb, text)

    def _toggle_autoconnect(self, item: rumps.MenuItem) -> None:
        item.state = not item.state
        if self._watchdog is None:
            self._enter_disconnected_state()

    def _connect_now(self, _item) -> None:
        self._retry_ticks = RETRY_TICKS
        if self._watchdog is None and not self._try_connect():
            self._set_status("Pico not found", _RED)

    def _open_github(self, _item) -> None:
        webbrowser.open(github_update.REPO_URL)

    def _about(self, _item) -> None:
        rumps.alert(title="DIY StreamDeck", message=f"Version {VERSION}")

    def _toggle_login_item(self, item: rumps.MenuItem) -> None:
        try:
            if item.state:
                login_item.disable()
                item.state = False
            else:
                login_item.enable()
                item.state = True
        except OSError as e:
            self._set_status(f"Login item failed: {e}", _RED)
            item.state = login_item.is_enabled()

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
