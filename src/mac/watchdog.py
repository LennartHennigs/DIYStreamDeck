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
from src.mac.plugins.base_plugin import BasePlugin
import threading
import time
from AppKit import NSWorkspaceDidTerminateApplicationNotification

VERSION = "1.2.2"
HEARTBEAT_INTERVAL = 2
SERIAL_CLOSE_GRACE_PERIOD = 0.3  # seconds to wait after BYE so Pico can read it before port closes
PICO_VIDS = (0x2E8A, 0x239A)  # Raspberry Pi / Adafruit (CircuitPython) USB vendor IDs

plugins_directory = os.path.dirname(os.path.abspath(__file__)) + '/plugins'
sys.path.append(plugins_directory)

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


def find_pico_port_by_ping(baud_rate: int, timeout: float = 1.0) -> Optional[str]:
    """Try each serial port; return first that replies PONG to a PING."""
    for port in serial.tools.list_ports.comports():
        try:
            with serial.Serial(port.device, baud_rate, timeout=timeout) as s:
                s.write(b"PING\n")
                response = s.readline().decode("utf-8", errors="ignore").strip()
                if response == "PONG":
                    return port.device
        except (serial.SerialException, OSError):
            continue
    return None


def find_pico_port(baud_rate: int) -> Optional[str]:
    """Auto-detect Pico port: VID match first, PING probe as fallback."""
    port = find_pico_port_by_vid()
    if port:
        return port
    return find_pico_port_by_ping(baud_rate)


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
    def _run_heartbeat_loop(self) -> None:
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
            ['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = osa.communicate(script.encode())
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
                self.ser.write(message.encode('utf-8'))
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


    # Run the NSRunLoop, polling serial each iteration
    def run_loop(self) -> None:
        ns_run_loop = Cocoa.NSRunLoop.currentRunLoop()
        while True:
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
    plugin_files = [f for f in os.scandir(full_path)
                    if f.is_file()
                    and f.name.endswith('.py')
                    and f.name not in ('base_plugin.py', '__init__.py')
                    and not f.name.startswith('.')]
    for plugin_file in plugin_files:
        plugin_name = os.path.splitext(plugin_file.name)[0]
        abs_path = os.path.join(full_path, plugin_file.name)

        # Stage 1: load the module
        try:
            spec = importlib.util.spec_from_file_location(plugin_name, abs_path)
            plugin_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin_module)
        except Exception as e:
            print(f"Error loading plugin module {plugin_name}: {e}")
            continue

        # Stage 2: locate config file
        central = os.path.join(base_path, 'plugins_config', f'{plugin_name}.json')
        fallback = os.path.join(full_path, 'config', f'{plugin_name}.json')
        if os.path.exists(central):
            config_path = central
            source = 'central'
        elif os.path.exists(fallback):
            config_path = fallback
            source = 'plugin-local'
        else:
            print(f"Skipping plugin '{plugin_name}': no config found at {central} or {fallback}")
            continue

        if verbose:
            print(f"Using {source} config for plugin '{plugin_name}': {config_path}")

        # Stage 3: instantiate
        try:
            plugin_class = getattr(plugin_module, f'{plugin_name.capitalize()}Plugin')
            plugins[plugin_name] = plugin_class(config_path, verbose)
            print(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            print(f"Error initializing plugin {plugin_name} (file={plugin_file.name}): {e}")
    print()
    return plugins


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
                        help='Rotation direction for the keypad (default: CW)')
    args = parser.parse_args()

    if args.port is None:
        args.port = find_pico_port(args.speed)
        if args.port is None:
            print("Error: Pico not found. Connect the device or specify --port.")
            return
        print(f"Auto-detected port: {args.port}")

    ser = create_serial_connection(args.port, args.speed)
    if ser is None:
        print("Error: No serial connection.")
        return

    print(f'Keypad watchdog {VERSION} is running...')

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
    frontmost = Cocoa.NSWorkspace.sharedWorkspace().frontmostApplication()
    if frontmost:
        watchdog.send_app_name_to_microcontroller(watchdog._get_app_name(frontmost))
    heartbeat_thread = threading.Thread(target=watchdog._run_heartbeat_loop)
    heartbeat_thread.start()

    if args.rotate:
        watchdog._serial_write(f'Rotate: {args.rotate}\n', 'Rotate')

    try:
        watchdog.run_loop()
    except KeyboardInterrupt:
        pass  # User pressed CTRL-C to exit
    except Exception as e:
        print(f"An error occurred during the execution: {e}")
    finally:
        notification_center.removeObserver_(watchdog)
        watchdog._stop_event.set()
        heartbeat_thread.join()   # stop heartbeat before BYE to avoid lock contention
        watchdog.send_bye()
        ser.flush()
        time.sleep(SERIAL_CLOSE_GRACE_PERIOD)
        ser.close()
        if args.verbose:
            print("Shutdown complete.")


# Entry point for the script
if __name__ == "__main__":
    main()
