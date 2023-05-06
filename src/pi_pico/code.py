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
import board


class KeyController:
    # https://docs.circuitpython.org/projects/hid/en/latest/_modules/adafruit_hid/keycode.html
    JSON_FILE = "key_def.json"

    KEYCODE_MAPPING = {name: getattr(Keycode, name) for name in dir(
        Keycode) if not name.startswith("__")}

    def __init__(self):
        self.keypad = RgbKeypad()
        self.keys = self.keypad.keys
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.key_configs, self.folders = self.read_key_configs(self.JSON_FILE)
        self.key_config = self.key_configs.get("_otherwise", {})
        self.usb_serial = usb_cdc.console
        self.update_keys()
        self.folder_open = False
        self.active_app = None


        
    def open_folder(self, folder_name):
        if folder_name in self.folders:
            self.folder_open = True
            self.folder_name = folder_name
            self.key_config = self.folders[folder_name]
            self.update_keys()

    def close_folder(self):
        self.folder_open = False
        self.key_config = self.key_configs.get(self.active_app, self.key_configs.get("_otherwise", {}))
        self.update_keys()

    def key_action(self, key, press=True):
        if key.number in self.key_config:
            key_sequences, color, _, _, action, _ = self.key_config[key.number]
            self.update_key_led(key, color, press)

            key_config_dict = dict(zip(['key_sequences', 'color', 'description', 'application', 'action', 'folder'], self.key_config[key.number]))

            if key_config_dict.get('action') and press:
                action = key_config_dict['action']
                if action == 'open_folder':
                    folder_name = key_config_dict['folder']
                    if folder_name in self.folders:
                        self.open_folder(folder_name)
                elif action == 'close_folder':
                    self.close_folder()
            else:
                self.handle_key_sequences(key_sequences, press)

                if isinstance(self.key_config[key.number], tuple):
                    if key_config_dict.get('application') and press:
                        app_name = key_config_dict['application']
                        self.send_application_name(app_name)

    def update_key_led(self, key, color, press):
        if key.number in self.key_config:
            _, color, _, _, _, _ = self.key_config[key.number]
            key.set_led(*color) if not press else key.led_off()
            if press:  # Only print the description when the key is pressed
                _, _, description, _, _, _ = self.key_config[key.number]
                #print(f"Key {key.number} pressed: {description}")

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
        for key in self.keys:
            if key.number in self.key_config:
                key_config_dict = dict(zip(['key_sequences', 'color', 'description', 'application', 'action', 'folder'], self.key_config[key.number]))

                color = key_config_dict['color']
                key.set_led(*color)
                self.keypad.on_press(key, self.key_action)
                self.keypad.on_release(
                    key, lambda key=key: self.key_action(key, press=False))
            else:
                key.led_off()
                self.keypad.on_press(key, lambda _, key=key: None)
                self.keypad.on_release(key, lambda _, key=key: None)


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
            usb_cdc.console.write(f"Launch: {app_name}\n".encode('utf-8'))  # Encode the string to bytes
            # print(f"Sent to Mac: Launch: {app_name}")
        except Exception as e:
            # print(f"Could not launch {app_name}: {e}\n")
            pass
    
    def run(self):
        while True:
            app_name = self.read_serial_line()
            if app_name is not None:
                #print(f"Active App: {app_name}")
                self.key_config = self.key_configs.get(
                    app_name, self.key_configs.get("_otherwise", {}))
                self.update_keys()
            else:
                time.sleep(0.1)
                self.keypad.update()

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
            return (0, 0, 0)

        def convert_value(value):
            if isinstance(value, str):
                return convert_keycode_string(value)
            return value

        with open(json_filename, 'r') as json_file:
            json_data = json.load(json_file)

        key_configs = {}
        folders = {}
        for app, configs in json_data["key_definitions"].items():
            key_configs[app] = {}
            for key, config in configs.items():
                key_sequence = config.get('key_sequence', [])
                key_sequences = tuple(convert_value(v) for v in key_sequence) if isinstance(
                    key_sequence, list) else convert_keycode_string(key_sequence)
                color_array = convert_color_string(config.get('color', ''))
                description = config.get('description', '')
                application = config.get('application', '')
                action = config.get('action', '')
                folder = config.get('folder', '')

                if action == 'open_folder' and folder not in json_data["folders"]:
                    print(f"Error: Folder '{folder}' not found. Disabling key binding.")
                    key_sequences = ()
                    color_array = (0,0,0)
                    description = ''
                    application = ''
                    action = ''
                    folder = ''
                else:
                    key_sequences, color_array, description, application, action, folder = (
                        key_sequences, color_array, description, application, action, folder)

                key_configs[app][int(key)] = (
                    key_sequences, color_array, description, application, action, folder)

        for folder_name, folder_configs in json_data["folders"].items():
            folders[folder_name] = {}
            close_folder_found = False
            for key, config in folder_configs.items():
                key_sequence = config.get('key_sequence', [])
                key_sequences = tuple(convert_value(v) for v in key_sequence) if isinstance(
                    key_sequence, list) else convert_keycode_string(key_sequence)
                color_array = convert_color_string(config.get('color', ''))
                description = config.get('description', '')
                application = config.get('application', '')
                action = config.get('action', '')
                folder = config.get('folder', '')

                if action == "close_folder":
                    close_folder_found = True

                folders[folder_name][int(key)] = (
                    key_sequences, color_array, description, application, action, folder)

            if not close_folder_found:
                raise ValueError(f"Error: Folder '{folder_name}' does not have a 'close_folder' action defined.")

        return key_configs, folders


if __name__ == "__main__":
    controller = KeyController()
    controller.run()


