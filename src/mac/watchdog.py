# DIY Streamdeck watchdog code for a Mac
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-05
# https://github.com/LennartHennigs/DIYStreamDeck

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
    def initWithSerial_args_(self, ser: serial.Serial, args):
        self = objc.super(AppObserver, self).init()
        if self is None:
            return None
        self.ser = ser
        self.args = args
        return self

    @objc.signature(b'v@:@')  # Encoded the signature string as bytes
    def applicationActivated_(self, notification):
        app_name = notification.userInfo(
        )['NSWorkspaceApplicationKey'].localizedName()
        self.send_app_name_to_microcontroller(app_name)

    @objc.signature(b'v@:@')
    def send_app_name_to_microcontroller(self, app_name):
        script = None
        if app_name == "Google Chrome":
            script = '''
                tell application "Google Chrome"
                    get URL of active tab of first window
                end tell
            '''
        elif app_name == "Safari":
            script = '''
                tell application "Safari"
                    get URL of current tab of front window
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

    ser = create_serial_connection(args.port, args.speed)
    if ser is None:
        print(" Failed to create serial connection.")
        return

    print()
    print("RGB Keypad watchdog is running...")
    app_observer = AppObserver.alloc().initWithSerial_args_(ser, args)
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

    print("Good bye!")
    print()


# Entry point for the script
if __name__ == "__main__":
    main()
