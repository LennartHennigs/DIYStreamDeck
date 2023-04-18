# DIY Steamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0 
# last changed: 23-04-14
# https://github.com/LennartHennigs/DIYStreamDeck

import time
import json
from rgbkeypad import RgbKeypad
import usb_hid
import usb_cdc
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
import board

class KeyController:
    JSON_FILE = "key_def.json"

    KEYCODE_MAPPING = {name: getattr(Keycode, name) for name in dir(Keycode) if not name.startswith("__")}

    def __init__(self):
        self.keypad = RgbKeypad()
        self.keys = self.keypad.keys
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.key_configs = self.read_key_configs(self.JSON_FILE)
        self.key_config = self.key_configs.get("_otherwise", {})  # Add this line to set the initial key configuration
        self.usb_serial = usb_cdc.console
        self.update_keys()

    def key_action(self, key, press=True):
        if key.number in self.key_config:
            key_sequences, color = self.key_config[key.number]
            self.update_key_led(key, color, press)
            self.handle_key_sequences(key_sequences, press)

    def update_key_led(self, key, color, press):
        key.set_led(*color) if not press else key.led_off()

    def handle_key_sequences(self, key_sequences, press):
        for item in key_sequences:
            if isinstance(item, float):
                self.keyboard.release_all()
                time.sleep(item)
            elif isinstance(item, tuple):
                self.keyboard.press(*item) if press else self.keyboard.release(*item)
            else:
                self.keyboard.press(item) if press else self.keyboard.release(item)

    def update_keys(self):
        for key in self.keys:
            if key.number in self.key_config:
                key.set_led(*self.key_config[key.number][1])
                self.keypad.on_press(key, self.key_action)
                self.keypad.on_release(key, lambda key: self.key_action(key, press=False))
            else:
                key.led_off()
                self.keypad.on_press(key, lambda _: None)
                self.keypad.on_release(key, lambda _: None)

    def read_serial_line(self):
        if usb_cdc.console.in_waiting > 0:
            raw_data = usb_cdc.console.readline()
            try:
                return raw_data.decode("utf-8").strip()
            except UnicodeDecodeError:
                pass
        return None

    def run(self):
        while True:
            app_name = self.read_serial_line()
            if app_name is not None:
                print(app_name)
                self.key_config = self.key_configs.get(app_name, self.key_configs.get("_otherwise", {}))
                self.update_keys()
            else:
                time.sleep(0.1)
                self.keypad.update()

    def read_key_configs(self, json_filename):
        def convert_keycode_string(keycode_string):
            keycode_list = keycode_string.split('+')
            return tuple(self.KEYCODE_MAPPING[key] for key in keycode_list)

        def convert_color_string(color_string):
            if color_string.startswith("#"):
                return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
            return None

        def convert_value(value):
            if isinstance(value, str):
                return convert_keycode_string(value)
            return value

        with open(json_filename, 'r') as json_file:
            json_data = json.load(json_file)

        key_configs = {}
        for app, configs in json_data.items():
            key_configs[app] = {}
            for key, key_sequence_and_color in configs.items():
                key_sequences = tuple(convert_value(v) for v in key_sequence_and_color[0]) if isinstance(key_sequence_and_color[0], list) else convert_keycode_string(key_sequence_and_color[0])
                color_array = convert_color_string(key_sequence_and_color[1])
                key_configs[app][int(key)] = (key_sequences, color_array)
        return key_configs

if __name__ == "__main__":
    controller = KeyController()
    controller.run()
