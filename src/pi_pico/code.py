# DIY Streamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-05
# https://github.com/LennartHennigs/DIYStreamDeck

import time
import json
from rgbkeypad import RgbKeypad
import usb_hid
import usb_cdc
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode


class KeyController:
    JSON_FILE = "key_def.json"

    KEYCODE_MAPPING = {name: getattr(Keycode, name) for name in dir(
        Keycode) if not name.startswith("__")}

    def __init__(self):
        self.keypad = RgbKeypad()
        self.keys = self.keypad.keys
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.key_configs = self.read_key_configs(self.JSON_FILE)
        self.key_config = self.key_configs.get("_otherwise", {})
        self.usb_serial = usb_cdc.console
        self.update_keys()

    def key_action(self, key, press=True):
        if key.number in self.key_config:
            key_sequences, color, _, _ = self.key_config[key.number]
            self.update_key_led(key, color, press)
            self.handle_key_sequences(key_sequences, press)
            app_config = self.key_config[key.number]
            if 'application' in app_config:
                self.send_application_name(app_config['application'])

    def update_key_led(self, key, color, press):
        key.set_led(*color) if not press else key.led_off()
        if press:
            _, _, description, _ = self.key_config[key.number]
            print(f"Key {key.number} pressed: {description}")

    def handle_key_sequences(self, key_sequences, press):
        for item in key_sequences:
            if isinstance(item, float):
                self.keyboard.release_all()
                time.sleep(item)
            elif isinstance(item, tuple):
                self.keyboard.press(
                    *item) if press else self.keyboard.release(*item)
            else:
                self.keyboard.press(
                    item) if press else self.keyboard.release(item)

    def update_keys(self):
        def do_nothing(key):
            pass

        for key in self.keys:
            if key.number in self.key_config:
                key.set_led(*self.key_config[key.number][1])
                self.keypad.on_press(key, self.key_action)
                self.keypad.on_release(
                    key, lambda key: self.key_action(key, press=False))
            else:
                key.led_off()
                self.keypad.on_press(key, do_nothing)
                self.keypad.on_release(key, do_nothing)

    def read_serial_line(self):
        if usb_cdc.console.in_waiting > 0:
            raw_data = usb_cdc.console.readline()
            try:
                return raw_data.decode("utf-8").strip()
            except UnicodeDecodeError:
                pass
        return None

    def send_application_name(self, app_name):
        try:
            with self.usb_serial as serial:
                serial.write(f"Launch: {app_name}\n")
            if print(f"Sent to Mac: Launch: {app_name}")
        except Exception as e:
            print(f"Could not launch {app_name}: {str(e)}\n")

    def run(self):
        while True:
            app_name = self.read_serial_line()
            if app_name is not None:
                print(f"Active App: {app_name}")
                self.key_config = self.key_configs.get(
                    app_name, self.key_configs.get("_otherwise", {}))
                self.update_keys()
            else:
                time.sleep(0.1)
                self.keypad.update()

    def read_key_configs(self, json_filename):
       

def read_key_configs(self, json_filename):
        def convert_keycode_string(keycode_string):
            keycode_list = keycode_string.split('+')
            keycodes = []
            for key in keycode_list:
                if key not in self.KEYCODE_MAPPING:
                    raise ValueError(
                        f"Unknown keycode constant: {key} in '{keycode_string}'")
                keycodes.append(self.KEYCODE_MAPPING[key])
            return tuple(keycodes)

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
            for key, config in configs.items():
                key_sequence = config.get('key_sequence', [])
                key_sequences = tuple([convert_value(v) for v in key_sequence])
                color_array = None
                if 'color' in config:
                    color_array = convert_color_string(config['color'])
                description = config.get('description', '')
                application = config.get('application', '')
                key_configs[app][int(key)] = (
                    key_sequences, color_array, description, application)
        return key_configs


if __name__ == "__main__":
    controller = KeyController()
    controller.run()
