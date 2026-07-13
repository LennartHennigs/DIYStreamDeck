# DIY Streamdeck watchdog code for a Mac
# L. Hennigs and ChatGPT 4.0
# last changed: 01-31-24
# https://github.com/LennartHennigs/DIYStreamDeck

import sys
import Cocoa
import serial
import serial.tools.list_ports
import objc
import argparse
import re
import subprocess
from inspect import signature
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import importlib.util
import os
from src.mac import config_paths
from src.mac.plugins.base_plugin import BasePlugin
import threading
import time
from AppKit import NSWorkspaceDidTerminateApplicationNotification

VERSION = "1.2.2"
HEARTBEAT_INTERVAL = 2
SERIAL_CLOSE_GRACE_PERIOD = 0.3  # seconds to wait after BYE so Pico can read it before port closes
PICO_VIDS = (0x2E8A, 0x239A)  # Raspberry Pi / Adafruit (CircuitPython) USB vendor IDs

def create_serial_connection(port: str, baud_rate: int) -> Optional[serial.Serial]:
    try:
        return serial.Serial(port, baud_rate, timeout=1)
    except serial.SerialException:
        return None


def find_pico_port_by_vid() -> Optional[str]:
    """Return first serial port with a known Pico/CircuitPython VID, or None."""
    for port in serial.tools.list_ports.comports():
        if port.vid in PICO_VIDS:
            return port.device
    return None


class WatchDog(Cocoa.NSObject):
    ser: serial.Serial
    args: argparse.Namespace
    plugins: Dict[str, BasePlugin]
    launch_pattern = re.compile(r"^Launch: (.+)$")
    run_pattern = re.compile(r"^Run: (.+)$")
    output_pattern = re.compile(r"^Output: (.+)$")
    unsafe_app_name_pattern = re.compile(r"^-|[/\\\x00]")  # leading dash → flag injection; / \ \x00 → path traversal

    # Initializer
    def initWithSerial_args_plugins_(self, ser: serial.Serial, args: argparse.Namespace, plugins: Dict[str, Any]) -> Optional['WatchDog']:
        self = objc.super(WatchDog, self).init()
        if self is None:
            return None
        self.ser = ser
        self.args = args
        self.plugins = plugins
        self._serial_lock = threading.Lock()
        self._stop_event = threading.Event()
        # Set when the serial port dies; ends the session so main() can reconnect
        self._disconnected = threading.Event()
        # Optional observer fired on real app changes (menu-bar cheat sheet)
        self.on_app_changed = None
        # Dedup state for send_app_name_to_microcontroller — see there.
        self._last_sent_app_name = None
        # Add observer for application termination
        Cocoa.NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
            self,
            self.applicationTerminated_,
            NSWorkspaceDidTerminateApplicationNotification,
            None
        )
        return self

    def _get_app_name(self, app) -> str:
        """Extract a display name from an NSRunningApplication object."""
        name = app.localizedName() or app.bundleIdentifier() or app.bundleExecutable()
        return name or "unknown"

    # Called when an application is terminated
    @objc.typedSelector(b'v@:@')  # Encoded the signature string as bytes
    def applicationTerminated_(self, notification: Cocoa.NSNotification) -> None:
        app = notification.userInfo()['NSWorkspaceApplicationKey']
        app_name = self._get_app_name(app)
        # send the app name to the keypad
        self._serial_write("Terminated: " + app_name + '\n', "Terminated")
        # If the app that just died is the one currently shown, clear the App:
        # dedup so a same-named relaunch that regains focus without an
        # intervening app switch re-sends its layout instead of being suppressed.
        if app_name == self._last_sent_app_name:
            self._last_sent_app_name = None


    # Called every HEARTBEAT_INTERVAL seconds
    def _run_heartbeat_loop(self) -> None:
        while not self._stop_event.wait(HEARTBEAT_INTERVAL):
            if self._disconnected.is_set():
                return  # port is gone — stop instead of spamming errors
            # Send a framed heartbeat message so the keypad can detect liveness
            self._serial_write('HB\n', 'HB')


    # Called when the active application changes
    @objc.typedSelector(b'v@:@')  # Encoded the signature string as bytes
    def applicationActivated_(self, notification: Cocoa.NSNotification) -> None:
        app = notification.userInfo()['NSWorkspaceApplicationKey']
        # Never react to our own process (menu-bar app's About window, running
        # unbundled as "Python") — the keypad must keep showing the real app.
        if app.processIdentifier() == os.getpid():
            return
        app_name = self._get_app_name(app)
        self.send_app_name_to_microcontroller(app_name)


    # Get the URL of the active tab in Google Chrome or Safari
    def get_url(self, app_name) -> str:
        command_dict = {
            "Google Chrome": '''
                if (count of windows) > 0 then
                    get URL of active tab of first window
                else
                    return ""
                end if
            ''',
            "Safari": '''
                if (count of windows) > 0 then
                    get URL of current tab of front window
                else
                    return ""
                end if
            '''
        }
        # Only proceed for known-safe app names (prevents AppleScript injection)
        if app_name not in command_dict:
            return ""
        safe_app_name = app_name.replace('"', '\\"')
        script = f'''
            tell application "{safe_app_name}"
                {command_dict[app_name]}
            end tell
        '''
        osa = subprocess.Popen(
            ['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # runs on the main thread — a hung osascript must not freeze the run loop
            output, error = osa.communicate(script.encode(), timeout=2)
        except subprocess.TimeoutExpired:
            osa.kill()
            osa.communicate()
            if self.args.verbose:
                print(f"osascript timed out querying {app_name}")
            return ""
        if error and self.args.verbose:
            print(f"osascript error: {error.decode().strip()}")
        full_url = output.decode().strip()

        if full_url:
            parsed_url = urlparse(full_url)
            base_url = parsed_url.netloc

            # If base_url is 'newtab' for Google Chrome or empty for Safari, don't add it in brackets
            if not (app_name == "Google Chrome" and base_url == "newtab") and base_url != "":
                return " (" + base_url + ")"

        return ""



    # Send the name of the active application to the keypad via serial
    def send_app_name_to_microcontroller(self, app_name: str) -> None:
        if app_name in ["Safari", "Google Chrome"]:
            app_name = app_name + self.get_url(app_name)

        # Suppress redundant activations. macOS fires
        # NSWorkspaceDidActivateApplicationNotification on many events that don't
        # actually change the active app (window focus flicker, background helpers,
        # Terminal foreground/background). Sending duplicate App: lines forces the
        # Pico to repaint every key via update_keys(), which visibly wipes any
        # active Claude signal color and burns cycles for no functional gain.
        if app_name == self._last_sent_app_name:
            return
        self._last_sent_app_name = app_name

        if self.args.verbose:
            print(f'Active app: {app_name}')
        self._serial_write("App: " + app_name + '\n', "App")

        # Optional observer (menu-bar app's cheat sheet); fires only on real
        # app changes thanks to the dedup above. getattr: test instances are
        # built via object.__new__ and may lack the attribute.
        callback = getattr(self, 'on_app_changed', None)
        if callback:
            callback(app_name)

    # Flag the serial port as dead exactly once (ends the current session)
    def _mark_disconnected(self, error: Exception) -> None:
        if not self._disconnected.is_set():
            print(f"Serial connection lost: {error}")
            self._disconnected.set()

    # Send a HELLO or BYE message so the keypad can react to clean startup/shutdown
    def _serial_write(self, message: str, label: str) -> None:
        with self._serial_lock:
            if self._disconnected.is_set():
                return
            try:
                self.ser.write(message.encode('utf-8'))
            except (serial.SerialException, OSError) as e:
                self._mark_disconnected(e)
            except Exception as e:
                print(f"Error sending {label}: {e}")

    def send_hello(self) -> None:
        self._serial_write(f"HELLO:{VERSION}\n", "HELLO")

    def send_bye(self) -> None:
        self._serial_write("BYE\n", "BYE")

    # Exposed to plugins (via BasePlugin.on_watchdog_start(send_to_keypad)) so
    # background listeners can push single lines to the Pico under the watchdog's lock.
    def _send_line_to_keypad(self, line: str) -> None:
        self._serial_write(line, "plugin")


    # Read data from the serial connection from the keypad
    def read_serial_data(self) -> Optional[str]:
        try:
            if self.ser.in_waiting == 0:
                return
            # errors="replace": one junk byte must not kill the run loop
            return self.ser.readline().decode(errors="replace").strip()
        except (serial.SerialException, OSError) as e:
            self._mark_disconnected(e)
            return


    # Launch an application
    def launch_app(self, match: re.Match) -> None:
        launch_app_name = match.group(1)
        # Leading dash injects flags into `open -a`; / \ \x00 are path traversal / null injection
        if self.unsafe_app_name_pattern.search(launch_app_name):
            print(f"Refused unsafe app name: {launch_app_name!r}")
            return
        if self.args.verbose:
            print(f"Launching: {launch_app_name}")
        try:
            subprocess.run(["open", "-a", launch_app_name], check=True)
        except subprocess.CalledProcessError as e:
            if self.args.verbose:
                print(f"Failed to launch '{launch_app_name}': {e}")


    # Run a plugin command
    def run_plugin_command(self, match: re.Match) -> None:
        parts = match.group(1).split(' ', 1)
        command = parts[0].strip()
        param = parts[1].strip() if len(parts) > 1 else None
        plugin = self.plugins.get(command.split('.')[0])

        # Check if the plugin exists
        if not plugin:
            if self.args.verbose:
                print(f"Plugin {command.split('.')[0]} not found")
            return
        # Check if the plugin command exists
        commands = plugin.commands()
        if command not in commands:
            if self.args.verbose:
                print(f"Command {command} not found")
            return
        # Check if the command requires a parameter (defaults make it optional)
        command_func = commands[command]
        required_params = [p for p in signature(command_func).parameters.values()
                           if p.default is p.empty]
        if required_params and param is None:
            if self.args.verbose:
                print(f"Parameter missing for command: {command}")
            return
        # Parse parameter
        if param is not None:
            if param.startswith("'") and param.endswith("'"):  # String parameter
                param = param[1:-1]  # Remove single quotes
            else:  # Integer parameter
                try:
                    param = int(param)
                except ValueError:
                    if self.args.verbose:
                        print(f"Invalid parameter: {param}")
                    return
        if self.args.verbose:
            print(f"Executing: {command}")  # Echo when a command is detected
        command_func(param) if param is not None else command_func()


    # Run the NSRunLoop, polling serial each iteration; returns on disconnect
    def run_loop(self) -> None:
        ns_run_loop = Cocoa.NSRunLoop.currentRunLoop()
        while not self._disconnected.is_set():
            ns_run_loop.runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.1))
            self.check_serial()


    # Check if there's any data in the serial buffer
    def check_serial(self) -> None:
        command = self.read_serial_data()
        if not command:
            return

        # Lightweight echo diagnostic: keypad -> "ECHO" or "ECHO:<token>"
        if command.upper().startswith('ECHO'):
            parts = command.split(':', 1)
            token = parts[1] if len(parts) > 1 else None
            reply = 'ECHO-OK' + (f':{token}' if token else '') + '\n'
            self._serial_write(reply, 'ECHO-OK')
            return

        for pattern, handler in (
            (self.launch_pattern, self.launch_app),
            (self.run_pattern,    self.run_plugin_command),
            (self.output_pattern, self.handle_output),
        ):
            match = re.match(pattern, command)
            if match:
                handler(match)
                return


    # Print a message forwarded from the Pico
    def handle_output(self, match: re.Match) -> None:
        print(f"[Pico] {match.group(1)}")


# Load all plugins
def load_plugins(path: str = 'plugins', verbose: bool = False) -> Dict[str, BasePlugin]:
    plugins = {}
    base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, path)

    # Only consider real plugin python files. Skip base_plugin, __init__.py, and hidden files.
    home = os.path.expanduser('~')
    plugin_files = [f for f in os.scandir(full_path)
                    if f.is_file()
                    and f.name.endswith('.py')
                    and f.name not in ('base_plugin.py', '__init__.py')
                    and not f.name.startswith('.')]
    for plugin_file in plugin_files:
        plugin_name = os.path.splitext(plugin_file.name)[0]
        abs_path = os.path.join(full_path, plugin_file.name)

        # Stage 1: locate config file — skip before importing the module so
        # plugins with missing optional dependencies don't produce noisy errors.
        candidates = [
            (os.path.join(config_paths.config_dir(), f'{plugin_name}.json'),     'user-config'),
            (os.path.join(base_path, 'plugins_config', f'{plugin_name}.json'), 'central'),
            (os.path.join(full_path, 'config', f'{plugin_name}.json'),          'plugin-local'),
            (os.path.join(home, 'Library', 'Application Support',
                          'DIYStreamDeck', 'plugins_config', f'{plugin_name}.json'), 'user-support'),
        ]
        for config_path, source in candidates:
            if os.path.exists(config_path):
                break
        else:
            paths = ', '.join(p for p, _ in candidates)
            print(f"Skipping plugin '{plugin_name}': no config found at {paths}")
            continue

        # Stage 2: config exists — now load the module
        try:
            spec = importlib.util.spec_from_file_location(plugin_name, abs_path)
            plugin_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin_module)
        except Exception as e:
            print(f"Error loading plugin module {plugin_name}: {e}")
            continue

        if verbose:
            print(f"Using {source} config for plugin '{plugin_name}': {config_path}")

        # Stage 3: instantiate — find the BasePlugin subclass defined in the
        # module (robust against naming, unlike capitalize()+'Plugin')
        try:
            plugin_class = next(
                obj for obj in vars(plugin_module).values()
                if isinstance(obj, type)
                and issubclass(obj, BasePlugin)
                and obj is not BasePlugin
                and obj.__module__ == plugin_module.__name__
            )
            plugins[plugin_name] = plugin_class(config_path, verbose)
            print(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            print(f"Error initializing plugin {plugin_name} (file={plugin_file.name}): {e}")
    print()
    return plugins


# Invoke a lifecycle hook on every plugin, isolating per-plugin failures
def _run_plugin_lifecycle(plugins: Dict[str, BasePlugin], method_name: str, *args) -> None:
    for name, plugin in plugins.items():
        try:
            getattr(plugin, method_name)(*args)
        except Exception as e:
            print(f"Plugin '{name}' {method_name} error: {e}")


# Single connection attempt: resolve the port and open it (None on failure)
def _attempt_connect(args: argparse.Namespace) -> Optional[serial.Serial]:
    port = args.port or find_pico_port_by_vid()
    if not port:
        return None
    return create_serial_connection(port, args.speed)


# Connect to the Pico. With reconnect enabled (the default) this polls with
# capped backoff until a device appears; with --no-reconnect it returns None
# immediately when no device is available.
def _connect_or_wait(args: argparse.Namespace) -> Optional[serial.Serial]:
    delay = 2.0
    waiting_reported = False
    while True:
        ser = _attempt_connect(args)
        if ser:
            print(f"Connected: {ser.port}")
            return ser
        if args.no_reconnect:
            print("Error: Pico not found. Connect the device or specify --port.")
            return None
        if not waiting_reported:
            print("Waiting for the Pico to appear...")
            waiting_reported = True
        time.sleep(delay)
        delay = min(delay * 1.5, 15.0)


# Start one serial session: handshake, observers, heartbeat, plugin lifecycle.
# The session protocol lives here (and in end_session) only — the CLI's
# run_session and the menu-bar app both build on these two helpers.
def start_session(ser: serial.Serial, args: argparse.Namespace,
                  plugins: Dict[str, BasePlugin],
                  on_app_changed=None) -> tuple:
    watchdog = WatchDog.alloc().initWithSerial_args_plugins_(ser, args, plugins)
    watchdog.on_app_changed = on_app_changed
    notification_center = Cocoa.NSWorkspace.sharedWorkspace().notificationCenter()
    notification_center.addObserver_selector_name_object_(
        watchdog,
        objc.selector(watchdog.applicationActivated_,
                      signature=b'v@:@'),
        Cocoa.NSWorkspaceDidActivateApplicationNotification,
        None,
    )
    # send HELLO so the keypad can know we started (repaints after reconnect too)
    watchdog.send_hello()
    frontmost = Cocoa.NSWorkspace.sharedWorkspace().frontmostApplication()
    if frontmost:
        watchdog.send_app_name_to_microcontroller(watchdog._get_app_name(frontmost))
    heartbeat_thread = threading.Thread(target=watchdog._run_heartbeat_loop)
    heartbeat_thread.start()

    if args.rotate:
        watchdog._serial_write(f'Rotate: {args.rotate}\n', 'Rotate')

    # Start service-style plugins (background listeners). Default
    # BasePlugin.on_watchdog_start is a no-op, so keypress-only plugins
    # (spotify/hue/sounds) are unaffected.
    _run_plugin_lifecycle(plugins, 'on_watchdog_start', watchdog._send_line_to_keypad)
    return watchdog, heartbeat_thread


# Tear down a session started by start_session. BYE is only sent when the
# port is still alive (send_bye and not disconnected).
def end_session(watchdog: 'WatchDog', heartbeat_thread: threading.Thread,
                plugins: Dict[str, BasePlugin], send_bye: bool = True) -> None:
    Cocoa.NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(watchdog)
    watchdog._stop_event.set()
    heartbeat_thread.join()   # stop heartbeat before BYE to avoid lock contention
    # Stop plugins before closing the port (they may want a final flush)
    _run_plugin_lifecycle(plugins, 'on_watchdog_stop')
    if send_bye and not watchdog._disconnected.is_set():
        watchdog.send_bye()
        try:
            watchdog.ser.flush()
            time.sleep(SERIAL_CLOSE_GRACE_PERIOD)
        except (serial.SerialException, OSError):
            pass
    try:
        watchdog.ser.close()
    except (serial.SerialException, OSError):
        pass


# Run one serial session; returns True if it ended because the port died
# (caller should reconnect), False on clean shutdown (Ctrl-C).
def run_session(ser: serial.Serial, args: argparse.Namespace,
                plugins: Dict[str, BasePlugin]) -> bool:
    watchdog, heartbeat_thread = start_session(ser, args, plugins)
    try:
        watchdog.run_loop()  # returns when the serial port dies
    except Exception as e:
        print(f"An error occurred during the execution: {e}")
    finally:
        end_session(watchdog, heartbeat_thread, plugins)
    return watchdog._disconnected.is_set()


# Main function
def main() -> None:
    parser = argparse.ArgumentParser(
        description='Monitor active app and send data to microcontroller')
    parser.add_argument('--port', default=None,
                        help='Serial port for the microcontroller (auto-detected if omitted)')
    parser.add_argument('--speed', type=int, default=9600,
                        help='Baud rate for the serial connection (default: 9600)')
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='Print the name of the current active window (default: False)')
    parser.add_argument('--rotate', choices=['CW', 'CCW'],
                        help='Rotation direction for the keypad (default: none)')
    parser.add_argument('--no-reconnect', action='store_true', default=False,
                        help='Exit when the Pico disconnects instead of waiting for it to return')
    args = parser.parse_args()

    print(f'Keypad watchdog {VERSION} is running...')
    config_paths.ensure_config_dir()  # create + seed ~/Documents/DIYStreamDeck
    plugins = load_plugins(verbose=args.verbose)

    try:
        while True:
            ser = _connect_or_wait(args)
            if ser is None:
                sys.exit(1)  # --no-reconnect and no device
            disconnected = run_session(ser, args, plugins)
            if not disconnected:
                break  # clean shutdown
            if args.no_reconnect:
                sys.exit(1)
            print("Pico disconnected — reconnecting...")
    except KeyboardInterrupt:
        pass  # User pressed CTRL-C to exit
    if args.verbose:
        print("Shutdown complete.")


# Entry point for the script
if __name__ == "__main__":
    main()
