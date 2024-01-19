# DIY Streamdeck watchdog code for a Mac
# L. Hennigs and ChatGPT 4.0
# last changed: 01-19-24
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
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
from urllib.parse import urlparse
import importlib.util
import os
from plugins.base_plugin import BasePlugin
import threading
import time
from AppKit import NSWorkspaceDidTerminateApplicationNotification

VERSION = "1.3.0"
HEARTBEAT_INTERVAL = 2

plugins_directory = os.path.dirname(os.path.abspath(__file__)) + '/plugins'
sys.path.append(plugins_directory)

def create_serial_connection(port: str, baud_rate: int) -> Optional[serial.Serial]:
    try:
        return serial.Serial(port, baud_rate, timeout=1)
    except serial.SerialException:
        return None


def run_loop(observer: 'WatchDog') -> None:
    run_loop = Cocoa.NSRunLoop.currentRunLoop()
    while True:
        run_loop.runMode_beforeDate_(
            Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.1))
        observer.check_serial()

class WatchDog(Cocoa.NSObject):
    ser: serial.Serial
    args: argparse.Namespace
    plugins: Dict[str, BasePlugin]
    launch_pattern = r"^Launch: (.+)$"
    run_pattern = r"^Run: (.+)$"
    running: bool = True

    # Initializer
    def initWithSerial_args_plugins_(self, ser: serial.Serial, args: argparse.Namespace, plugins: Dict[str, Any]) -> Optional['WatchDog']:
        self = objc.super(WatchDog, self).init()
        if self is None:
            return None
        self.ser = ser
        self.args = args
        self.plugins = plugins
        # Add observer for application termination
        Cocoa.NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
            self,
            self.applicationTerminated_,
            NSWorkspaceDidTerminateApplicationNotification,
            None
        )
        return self

    # Called when an application is terminated
    @objc.signature(b'v@:@')  # Encoded the signature string as bytes
    def applicationTerminated_(self, notification: Cocoa.NSNotification) -> None:
        app = notification.userInfo()['NSWorkspaceApplicationKey']
        app_name = app.localizedName()
        if not app_name:
            app_name = app.bundleIdentifier() or app.bundleExecutable()
#        if self.args.verbose:
#            print(f"{app_name} has been terminated")
        # send the app name to the keypad
        try:
            self.ser.write(("Terminated: " + app_name + '\n').encode('ascii', 'replace'))
        except (serial.SerialException, UnicodeEncodeError) as e:
            print(f"Error sending app name to microcontroller: {e}")


    # Ccalled every HEARTBEAT_INTERVAL seconds
    @objc.signature(b'v@:')  # Encoded the signature string as bytes
    def send_heartbeat(self) -> None:
        while self.running:
            try:
                self.ser.write('.\n'.encode('ascii', 'replace'))
            except (serial.SerialException, UnicodeEncodeError) as e:
                print(f"Error sending heartbeat to microcontroller: {e}")
            time.sleep(HEARTBEAT_INTERVAL)


    # Called when the active application changes
    @objc.signature(b'v@:@')  # Encoded the signature string as bytes
    def applicationActivated_(self, notification: Cocoa.NSNotification) -> None:
        app = notification.userInfo()['NSWorkspaceApplicationKey']
        app_name = app.localizedName()
        if not app_name:
            app_name = app.bundleIdentifier() or app.bundleExecutable()
        self.send_app_name_to_microcontroller(app_name)


    # Get the URL of the active tab in Google Chrome or Safari
    @objc.signature(b'v@:@')  # Encoded the signature string as bytes
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
        script = f'''
            tell application "{app_name}"
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
    @objc.signature(b'v@:@')
    def send_app_name_to_microcontroller(self, app_name: str) -> str:
        if app_name in ["Safari", "Google Chrome"]:
            app_name = app_name + self.get_url(app_name)

        if self.args.verbose:
            print(f'Active app: {app_name}')
        try:
            self.ser.write(("App: " + app_name + '\n').encode('ascii', 'replace'))
        except (serial.SerialException, UnicodeEncodeError) as e:
            print(f"Error sending app name to microcontroller: {e}")


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


    # Run a plugin command
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
        if self.args.verbose:
            print(f"Executing: {command}")  # Echo when a command is detected
        command_func(param) if param is not None else command_func()


    # Check if there's any data in the serial buffer
    def check_serial(self) -> None:
        # Check if there's any data in the buffer
        command = self.read_serial_data()
        if not command:
            return

        match = re.match(self.launch_pattern, command)
        if match:
            self.launch_app(match)
            return

        match = re.match(self.run_pattern, command)
        if match:
            self.run_plugin_command(match)
            return


# Load all plugins
def load_plugins(path: str = 'plugins', verbose: bool = False) -> Dict[str, BasePlugin]:
    plugins = {}
    base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, path)

    plugin_files = [f for f in os.scandir(full_path) if f.is_file() and f.name.endswith('.py') and f.name != 'base_plugin.py']
    for plugin_file in plugin_files:
        plugin_name, plugin_module = load_plugin_module(plugin_file, full_path)
        if plugin_module is None:
            continue

        try:
            plugin_class = getattr(plugin_module, f'{plugin_name.capitalize()}Plugin')
            plugins[plugin_name] = plugin_class(os.path.join(full_path, 'config', f'{plugin_name}.json'), verbose)
            print(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            print(f"Error initializing plugin {plugin_name}: {e}")
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

    try:
        with create_serial_connection(args.port, args.speed) as ser:
            print('Keypad watchdog {VERSION} is running...'.format(VERSION=VERSION))

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
            running = [True]
            heartbeat_thread = threading.Thread(target=watchdog.send_heartbeat)
            heartbeat_thread.start()

            if args.rotate :
                ser.write(f'Rotate: {args.rotate}\n'.encode('ascii', 'replace'))

            try:
                run_loop(watchdog)
            except KeyboardInterrupt:
                pass  # User pressed CTRL-C to exit
            except Exception as e:
                print(f"An error occurred during the execution: {e}")
            finally:
                notification_center.removeObserver_(watchdog)
                watchdog.running = False
                heartbeat_thread.join() 

    except TypeError:
        print("Error: No serial connection.")


# Entry point for the script
if __name__ == "__main__":
    main()
