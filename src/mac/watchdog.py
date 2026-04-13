# DIY Streamdeck watchdog code for a Mac
# L. Hennigs and ChatGPT 4.0
# last changed: 01-31-24
# https://github.com/LennartHennigs/DIYStreamDeck

import sys
import Cocoa
import serial
import objc
import argparse
import re
import subprocess
from inspect import signature
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
from urllib.parse import urlparse
import importlib.util
import os
from src.mac.plugins.base_plugin import BasePlugin
import threading
from AppKit import NSWorkspaceDidTerminateApplicationNotification

VERSION = "1.2.1"
HEARTBEAT_INTERVAL = 2

plugins_directory = os.path.dirname(os.path.abspath(__file__)) + '/plugins'
sys.path.append(plugins_directory)

def create_serial_connection(port: str, baud_rate: int) -> Optional[serial.Serial]:
    try:
        return serial.Serial(port, baud_rate, timeout=1)
    except serial.SerialException:
        return None


def run_loop(observer: 'WatchDog') -> None:
    ns_run_loop = Cocoa.NSRunLoop.currentRunLoop()
    while True:
        ns_run_loop.runMode_beforeDate_(
            Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.1))
        observer.check_serial()

class WatchDog(Cocoa.NSObject):
    ser: serial.Serial
    args: argparse.Namespace
    plugins: Dict[str, BasePlugin]
    launch_pattern = re.compile(r"^Launch: (.+)$")
    run_pattern = re.compile(r"^Run: (.+)$")
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


    # Called every HEARTBEAT_INTERVAL seconds
    @objc.typedSelector(b'v@:')  # Encoded the signature string as bytes
    def send_heartbeat(self) -> None:
        while not self._stop_event.wait(HEARTBEAT_INTERVAL):
            # Send a framed heartbeat message so the keypad can detect liveness
            self._serial_write('HB\n', 'HB')


    # Called when the active application changes
    @objc.typedSelector(b'v@:@')  # Encoded the signature string as bytes
    def applicationActivated_(self, notification: Cocoa.NSNotification) -> None:
        app = notification.userInfo()['NSWorkspaceApplicationKey']
        app_name = self._get_app_name(app)
        self.send_app_name_to_microcontroller(app_name)


    # Get the URL of the active tab in Google Chrome or Safari
    @objc.typedSelector(b'v@:@')  # Encoded the signature string as bytes
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
            ['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output, error = osa.communicate(script.encode())
        full_url = output.decode().strip()

        if full_url:
            parsed_url = urlparse(full_url)
            base_url = parsed_url.netloc

            # If base_url is 'newtab' for Google Chrome or empty for Safari, don't add it in brackets
            if not (app_name == "Google Chrome" and base_url == "newtab") and base_url != "":
                return " (" + base_url + ")"

        return ""



    # Send the name of the active application to the keypad via serial
    @objc.typedSelector(b'v@:@')
    def send_app_name_to_microcontroller(self, app_name: str) -> None:
        if app_name in ["Safari", "Google Chrome"]:
            app_name = app_name + self.get_url(app_name)

        if self.args.verbose:
            print(f'Active app: {app_name}')
        self._serial_write("App: " + app_name + '\n', "App")

    # Send a HELLO or BYE message so the keypad can react to clean startup/shutdown
    def _serial_write(self, message: str, label: str) -> None:
        with self._serial_lock:
            try:
                self.ser.write(message.encode('ascii', 'replace'))
            except Exception as e:
                print(f"Error sending {label}: {e}")

    def send_hello(self) -> None:
        self._serial_write(f"HELLO:{VERSION}\n", "HELLO")

    def send_bye(self) -> None:
        self._serial_write("BYE\n", "BYE")


    # Read data from the serial connection from the keypad
    def read_serial_data(self) -> Optional[str]:
        if self.ser.in_waiting == 0:
            return
        try:
            return self.ser.readline().decode().strip()
        except serial.SerialException as e:
            print(f"Error reading from microcontroller: {e}")
            return


    # Launch an application
    @objc.typedSelector(b'v@:@')
    def launch_app(self, match: re.Match) -> None:
        launch_app_name = match.group(1)
        # Leading dash injects flags into `open -a`; / \ \x00 are path traversal / null injection
        if self.unsafe_app_name_pattern.search(launch_app_name):
            if self.args.verbose:
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
    @objc.typedSelector(b'v@:@')
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
        # Check if the command requires a parameter
        command_func = commands[command]
        if len(signature(command_func).parameters) > 0 and param is None:
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
                    print(f"Invalid parameter: {param}")
                    return
        if self.args.verbose:
            print(f"Executing: {command}")  # Echo when a command is detected
        command_func(param) if param is not None else command_func()


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
        ):
            match = re.match(pattern, command)
            if match:
                handler(match)
                return


# Load all plugins
def load_plugins(path: str = 'plugins', verbose: bool = False) -> Dict[str, BasePlugin]:
    plugins = {}
    base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, path)

    # Only consider real plugin python files. Skip base_plugin, __init__.py, and hidden files.
    plugin_files = [f for f in os.scandir(full_path)
                    if f.is_file()
                    and f.name.endswith('.py')
                    and f.name not in ('base_plugin.py', '__init__.py')
                    and not f.name.startswith('.')]
    for plugin_file in plugin_files:
        plugin_name, plugin_module = load_plugin_module(plugin_file, full_path)
        if plugin_module is None:
            continue

        try:
            plugin_class = getattr(plugin_module, f'{plugin_name.capitalize()}Plugin')
            # Prefer centralized config in src/mac/plugins_config if present
            # base_path is already the absolute path to src/mac
            central = os.path.join(base_path, 'plugins_config', f'{plugin_name}.json')
            fallback = os.path.join(full_path, 'config', f'{plugin_name}.json')

            # Choose which config to use, if any
            if os.path.exists(central):
                config_path = central
                source = 'central'
            elif os.path.exists(fallback):
                config_path = fallback
                source = 'plugin-local'
            else:
                # Neither config exists; skip loading this plugin and log a helpful message
                print(f"Skipping plugin '{plugin_name}': no config found at {central} or {fallback}")
                continue

            # Log the config path being used for easier debugging
            if verbose:
                print(f"Using {source} config for plugin '{plugin_name}': {config_path}")

            plugins[plugin_name] = plugin_class(config_path, verbose)
            print(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            print(f"Error initializing plugin {plugin_name} (file={plugin_file.name}): {e}")
    print()
    return plugins


# Load a plugin module
def load_plugin_module(plugin_file: str, full_path: str) -> Tuple[str, Any]:
    plugin_name = os.path.splitext(plugin_file.name)[0]
    abs_path = os.path.join(full_path, plugin_file.name)
    try:
        spec = importlib.util.spec_from_file_location(plugin_name, abs_path)
        plugin_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin_module)
    except Exception as e:
        print(f"Error loading plugin module {plugin_name}: {e}")
        return None, None

    return plugin_name, plugin_module


# Main function
def main() -> None:
    parser = argparse.ArgumentParser(
        description='Monitor active app and send data to microcontroller')
    parser.add_argument('--port', required=True,
                        help='Serial port for the microcontroller')
    parser.add_argument('--speed', type=int, default=9600,
                        help='Baud rate for the serial connection (default: 9600)')
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='Print the name of the current active window (default: False)')
    parser.add_argument('--rotate', choices=['CW', 'CCW'],
                        help='Rotation direction for the keypad (default: CW)')
    args = parser.parse_args()

    ser = create_serial_connection(args.port, args.speed)
    if ser is None:
        print("Error: No serial connection.")
        return

    print(f'\nKeypad watchdog {VERSION} is running...')

    plugins = load_plugins(verbose=args.verbose)
    watchdog = WatchDog.alloc().initWithSerial_args_plugins_(ser, args, plugins)
    notification_center = Cocoa.NSWorkspace.sharedWorkspace().notificationCenter()
    notification_center.addObserver_selector_name_object_(
        watchdog,
        objc.selector(watchdog.applicationActivated_,
                      signature=b'v@:@'),
        Cocoa.NSWorkspaceDidActivateApplicationNotification,
        None,
    )
    # send HELLO so the keypad can know we started
    watchdog.send_hello()
    heartbeat_thread = threading.Thread(target=watchdog.send_heartbeat)
    heartbeat_thread.start()

    if args.rotate:
        ser.write(f'Rotate: {args.rotate}\n'.encode('ascii', 'replace'))

    try:
        run_loop(watchdog)
    except KeyboardInterrupt:
        pass  # User pressed CTRL-C to exit
    except Exception as e:
        print(f"An error occurred during the execution: {e}")
    finally:
        notification_center.removeObserver_(watchdog)
        watchdog._stop_event.set()
        # send a clean BYE
        watchdog.send_bye()
        heartbeat_thread.join()


# Entry point for the script
if __name__ == "__main__":
    main()
