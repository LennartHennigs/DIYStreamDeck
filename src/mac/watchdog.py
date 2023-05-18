# DIY Streamdeck watchdog code for a Mac
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck

import sys
import Cocoa
import serial
import objc
import sys
import termios
import tty
import argparse
import re
import subprocess
from typing import Optional
from contextlib import contextmanager
from urllib.parse import urlparse
import importlib.util
import os


plugins_directory = os.path.dirname(os.path.abspath(__file__)) + '/plugins'
sys.path.append(plugins_directory)

# Function to create a serial connection


def create_serial_connection(port: str, baud_rate: int) -> Optional[serial.Serial]:
    try:
        return serial.Serial(port, baud_rate, timeout=1)
    except serial.SerialException:
        return None


# Function to run the main loop


def run_loop(observer: 'AppObserver'):
    run_loop = Cocoa.NSRunLoop.currentRunLoop()
    while True:
        run_loop.runMode_beforeDate_(
            Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.1))

        observer.handle_launch_command()

# Main AppObserver class


class AppObserver(Cocoa.NSObject):
    def initWithSerial_args_plugins_(self, ser: serial.Serial, args, plugins):
        self = objc.super(AppObserver, self).init()
        if self is None:
            return None
        self.ser = ser
        self.args = args
        self.plugins = plugins
        return self

    @objc.signature(b'v@:@')  # Encoded the signature string as bytes
    def applicationActivated_(self, notification):
        app_name = notification.userInfo(
        )['NSWorkspaceApplicationKey'].localizedName()
        self.send_app_name_to_microcontroller(app_name)

    @objc.signature(b'v@:@')
    def send_app_name_to_microcontroller(self, app_name):
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

    
    def handle_launch_command(self):
        launch_pattern = r"^Launch: (.+)$"
        run_pattern = r"^Run: (.+)$"

        # Check if there's any data in the buffer
        if self.ser.in_waiting > 0:
            try:
                command = self.ser.readline().decode().strip()
            except serial.SerialException as e:
                print(f"Error reading from microcontroller: {e}")
                return

            match = re.match(launch_pattern, command)
            if match:
                launch_app_name = match.group(1)
                if self.args.verbose:
                    print(f"Launching: {launch_app_name}")
                try:
                    subprocess.run(["open", "-a", launch_app_name], check=True)
                except subprocess.CalledProcessError as e:
                    pass
            else:
                match = re.match(run_pattern, command)
                if match:
                    plugin_command = match.group(1)
                    plugin_name, command_name = plugin_command.split('.')
                    if plugin_name in self.plugins:
                        plugin = self.plugins[plugin_name]
                        if plugin_command in plugin.commands():
                            if self.args.verbose:
                                print(f"Executing: {plugin_command}")  # Echo when a command is detected
                            plugin.commands()[plugin_command]()
                        else:
                            print(f"Command {plugin_command} not found")
                    else:
                        print(f"Plugin {plugin_name} not found")
                else: 
                    print(f"Unknown command {plugin_command}")


def load_plugins(path='plugins', verbose=False):
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

def main():
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
        print("Error: Lost serial connection.")

# Entry point for the script
if __name__ == "__main__":
    main()
