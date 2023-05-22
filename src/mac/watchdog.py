# DIY Streamdeck watchdog code for a Mac
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck

import sys
import Cocoa
import serial
import objc
import termios
import tty
import argparse
import re
import subprocess
from inspect import signature
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from urllib.parse import urlparse
import importlib.util
import os
from plugins.base_plugin import BasePlugin


plugins_directory = os.path.dirname(os.path.abspath(__file__)) + '/plugins'
sys.path.append(plugins_directory)


# Function to create a serial connection


def create_serial_connection(port: str, baud_rate: int) -> Optional[serial.Serial]:
    try:
        return serial.Serial(port, baud_rate, timeout=1)
    except serial.SerialException:
        return None


# Function to run the main loop


def run_loop(observer: 'AppObserver') -> None:
    run_loop = Cocoa.NSRunLoop.currentRunLoop()
    while True:
        run_loop.runMode_beforeDate_(
            Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.1))
        observer.check_serial()

class AppObserver(Cocoa.NSObject):
    ser: serial.Serial
    args: argparse.Namespace
    plugins: Dict[str, BasePlugin]
    launch_pattern = r"^Launch: (.+)$"
    run_pattern = r"^Run: (.+)$"


    def initWithSerial_args_plugins_(self, ser: serial.Serial, args: argparse.Namespace, plugins: Dict[str, Any]) -> Optional['AppObserver']:
        self = objc.super(AppObserver, self).init()
        if self is None:
            return None
        self.ser = ser
        self.args = args
        self.plugins = plugins
        return self


    @objc.signature(b'v@:@')  # Encoded the signature string as bytes
    def applicationActivated_(self, notification: Cocoa.NSNotification) -> None:
        app_name = notification.userInfo(
        )['NSWorkspaceApplicationKey'].localizedName()
        self.send_app_name_to_microcontroller(app_name)


    @objc.signature(b'v@:@')
    def send_app_name_to_microcontroller(self, app_name: str) -> None:
        command_dict = {
            "Google Chrome": 'get URL of active tab of first window',
            "Safari": 'get URL of current tab of front window'
        }

        script = None
        if app_name in command_dict:
            script = f'''
                tell application "{app_name}"
                    {command_dict[app_name]}
                end tell
            '''

        if script is not None:
            osa = subprocess.Popen(
                ['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            output, error = osa.communicate(script.encode())
            full_url = output.decode().strip()

            parsed_url = urlparse(full_url)
            base_url = parsed_url.netloc
            app_name = app_name + " (" + base_url + ")"

        if self.args.verbose:
            print(f'Active app: {app_name}')
        try:
            self.ser.write((app_name + '\n').encode('ascii', 'replace'))
        except (serial.SerialException, UnicodeEncodeError) as e:
            print(f"Error sending app name to microcontroller: {e}")

    
    def read_serial_data(self) -> Optional[str]:
        if self.ser.in_waiting == 0:
            return
        try:
            return self.ser.readline().decode().strip()
        except serial.SerialException as e:
            print(f"Error reading from microcontroller: {e}")
            return

    @objc.signature(b'v@:@')
    def launch_app(self, match: re.Match) -> None:
        launch_app_name = match.group(1)
        if self.args.verbose:
            print(f"Launching: {launch_app_name}")
        try:
            subprocess.run(["open", "-a", launch_app_name], check=True)
        except subprocess.CalledProcessError as e:
            pass
        return


    @objc.signature(b'v@:@')
    def run_plugin_command(self, match: re.Match) -> None:
        parts = match.group(1).split(' ', 1)
        command = parts[0].strip()
        param = parts[1].strip() if len(parts) > 1 else None
        plugin = self.plugins.get(command.split('.')[0])

        # Check if the plugin exists
        if not plugin:
            print(f"Plugin {command.split('.')[0]} not found")
            return

        # Check if the plugin command exists
        if command not in plugin.commands():
            print(f"Command {command} not found")
            return

        # Check if the command requires a parameter
        command_func = plugin.commands()[command]
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

#        if self.args.verbose:
#            print(f"Executing: {command}")  # Echo when a command is detected
        command_func(param) if param is not None else command_func()


    def check_serial(self) -> None:
        # Check if there's any data in the buffer
        command = self.read_serial_data()
        if not command:
            return

        match = re.match(self.launch_pattern, command)
        if match:
            print(f"App Launch")
            self.launch_app(match)
            return

        match = re.match(self.run_pattern, command)
        if match:
            print(f"Plugin Command")
            self.run_plugin_command(match)
            return


def load_plugins(path: str='plugins', verbose: bool=False) -> Dict[str, BasePlugin]:
    plugins = {}

    # Get the directory that contains the current script
    base_path = os.path.dirname(os.path.abspath(__file__))

    # Construct the full path to the plugins directory
    full_path = os.path.join(base_path, path)

    plugin_files = [f for f in os.scandir(full_path) if f.is_file() and f.name.endswith('.py') and f.name != 'base_plugin.py']
    for plugin_file in plugin_files:
        plugin_name = os.path.splitext(plugin_file.name)[0]

        abs_path = os.path.join(full_path, plugin_file.name)

        spec = importlib.util.spec_from_file_location(plugin_name, abs_path)
        plugin_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin_module)

        plugin_class = getattr(plugin_module, f'{plugin_name.capitalize()}Plugin')
        plugins[plugin_name] = plugin_class(os.path.join(full_path, 'config', f'{plugin_name}.json'), verbose)

        print(f"Loaded plugin: {plugin_name}")

    print()
    return plugins


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
    args = parser.parse_args()

    try:
        with create_serial_connection(args.port, args.speed) as ser:
            print("RGB Keypad watchdog is running...")

            plugins = load_plugins(verbose=args.verbose)

            app_observer = AppObserver.alloc().initWithSerial_args_plugins_(ser, args, plugins)
            notification_center = Cocoa.NSWorkspace.sharedWorkspace().notificationCenter()
            notification_center.addObserver_selector_name_object_(
                app_observer,
                objc.selector(app_observer.applicationActivated_, signature=b'v@:@'),
                Cocoa.NSWorkspaceDidActivateApplicationNotification,
                None,
            )

            try:
                run_loop(app_observer)
            except KeyboardInterrupt:
                pass  # User pressed CTRL-C to exit
            except Exception as e:
                print(f"An error occurred during the execution: {e}")
            finally:
                notification_center.removeObserver_(app_observer)

    except TypeError:
        print("Error: No serial connection.")

# Entry point for the script
if __name__ == "__main__":
    main()
