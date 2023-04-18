# DIY Steamdeck watchdog code for a Mac
# L. Hennigs and ChatGPT 4.0 
# last changed: 23-04-18
# https://github.com/LennartHennigs/DIYStreamDeck

import Cocoa
import serial
import objc
import sys
import termios
import tty
import argparse
from typing import Optional
from contextlib import contextmanager

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
        run_loop.runMode_beforeDate_(Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.1))

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
        self.send_app_name_to_microcontroller(notification)

    @objc.signature(b'v@:@')  # Encoded the signature string as bytes
    def send_app_name_to_microcontroller(self, notification):
        app_name = notification.userInfo()['NSWorkspaceApplicationKey'].localizedName()
        if self.args.verbose:
            print(f'Active app: {app_name}')
        try:
            self.ser.write((app_name + '\n').encode('ascii', 'replace'))
        except (serial.SerialException, UnicodeEncodeError) as e:
            print(f"Error sending app name to microcontroller: {e}")

# Main function
def main():
    parser = argparse.ArgumentParser(description='Monitor active app and send data to microcontroller')
    parser.add_argument('--port', required=True, help='Serial port for the microcontroller')
    parser.add_argument('--speed', type=int, default=9600, help='Baud rate for the serial connection (default: 9600)')
    parser.add_argument('--verbose', action='store_true', default=False, help='Print the name of the current active window (default: False)')
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
