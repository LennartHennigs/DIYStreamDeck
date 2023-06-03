# DIY Streamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0
# last changed: 23-06-03
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

    def __init__(self, verbose=False):
        self.verbose=verbose
        self.keypad = RgbKeypad()
        self.keys = self.keypad.keys
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.urls = {}
        self.key_configs, self.folders, self.global_config, self.urls = self.read_key_configs(self.JSON_FILE)
        self.key_config = self.key_configs.get("_otherwise", {})
        self.usb_serial = usb_cdc.console
        self.update_keys()
        self.folder_open = False
        self.active_app = None
        self.last_key_config = None
        self.folder_stack = [] 


    def open_folder(self, folder_name):
        if folder_name in self.folders:
            self.folder_stack.append({'folder_name': folder_name, 'last_key_config': self.key_config})
            self.folder_open = True
            self.key_config = self.folders[folder_name]
            self.update_keys()


    def close_folder(self):
        if not self.folder_stack:
            return
        last_folder = self.folder_stack.pop()
        self.folder_open = bool(self.folder_stack)
        self.key_config = last_folder['last_key_config']
        self.update_keys()


    def key_action(self, key, press=True):
        if key.number in self.key_config:
            key_config_dict = dict(zip(['key_sequences', 'color', 'description',
                                'application', 'action', 'folder'], self.key_config[key.number]))

            key_sequences = key_config_dict['key_sequences']
            color = key_config_dict['color']
            action = key_config_dict.get('action')
            folder = key_config_dict.get('folder')

            self.update_key_led(key, color, press)

            if press:
                if folder:
                    self.open_folder(folder)
                elif action == 'close_folder':
                    self.close_folder()
                else:
                    if isinstance(action, tuple):
                        self.send_plugin_command(*action)
                    app_name = key_config_dict.get('application')
                    if app_name:
                        self.send_application_name(app_name)
                        
            self.handle_key_sequences(key_sequences, press)


    def update_key_led(self, key, color, press):
        if key.number in self.key_config:
            key_config_dict = dict(zip(['key_sequences', 'color', 'description',
                                   'application', 'action', 'folder'], self.key_config[key.number]))

            color = key_config_dict['color']
            key.set_led(*color) if not press else key.led_off()
            if press:  # Only print the description when the key is pressed
                description = key_config_dict.get('description', '')
                # print(f"Key {key.number} pressed: {description}")


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
                key_config_dict = dict(zip(['key_sequences', 'color', 'description',
                                       'application', 'action', 'folder'], self.key_config[key.number]))

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
            usb_cdc.console.write(f"Launch: {app_name}\n".encode('utf-8'))
        except Exception as e:
            pass


    def send_plugin_command(self, plugin, command):
        try:
            usb_cdc.console.write(f"Run: {plugin}.{command}\n".encode('utf-8'))
        except Exception as e:
            pass


    def run(self):
        while True:
            raw_app_name = self.read_serial_line()
            if raw_app_name is not None:
                # Split the app_name string on the first occurrence of " ("
                split_app_name = raw_app_name.split(" (", 1)
                # The first part is always the app name
                app_name = split_app_name[0]
                # The second part is the details, if they exist
                url = None
                if len(split_app_name) > 1:
                    # Remove the trailing ")" from the details
                    url = split_app_name[1].rstrip(')')
                # Check if there is a keyboard definition for the URL
                if url in self.urls:
                    self.key_config = self.urls[url]
                else:
                    self.key_config = self.key_configs.get(app_name, self.key_configs.get("_otherwise", {}))
                self.update_keys()
            else:
                time.sleep(0.1)
                self.keypad.update()


    def convert_keycode_string(self, keycode_string):
        keycode_list = keycode_string.split('+')
        keycodes = []
        for key in keycode_list:
            if key not in self.KEYCODE_MAPPING:
                raise ValueError(
                    f"Unknown keycode constant: {key} in '{keycode_string}'")
            keycodes.append(self.KEYCODE_MAPPING[key])
        return tuple(keycodes)


    def convert_color_string(self, color_string):
        if color_string.startswith("#"):
            return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
        return (0, 0, 0)


    def convert_value(self, value):
        if isinstance(value, str):
            return self.convert_keycode_string(value)
        return value


    def get_config_items(self, config):
        key_sequence = config.get('key_sequence', [])
        key_sequences = tuple(self.convert_value(v) for v in key_sequence) if isinstance(
            key_sequence, list) else self.convert_keycode_string(key_sequence)
        color_array = self.convert_color_string(config.get('color', ''))
        description = config.get('description', '')
        application = config.get('application', '')
        action = config.get('action', '')
        if action and '.' in action:
            action = tuple(action.split('.',1))
        folder = config.get('folder', '')
        return key_sequences, color_array, description, application, action, folder


    def process_urls(self, json_data):
        urls = {}
        if "urls" in json_data:
            for url, configs in json_data["urls"].items():
                print(url);
                urls[url] = {}
                for key, config in configs.items():
                    key_sequences, color_array, description, application, action, folder = self.get_config_items(config)
                    urls[url][int(key)] = (key_sequences, color_array, description, application, action, folder)
        return urls
    

    def process_globals(self, json_data):
        global_config = {}
        if "global" in json_data:
            for key, config in json_data["global"].items():
                key_sequences, color_array, description, application, action, folder = self.get_config_items(config)
                if folder and folder not in json_data["folders"]:
                    print(
                        f"Error: Folder '{folder}' not found. Disabling key binding.")
                    key_sequences, color_array, description, application, action, folder = (
                        (), (0, 0, 0), '', '', '', '')
                global_config[int(key)] = (key_sequences, color_array, description, application, action, folder)
        return global_config


    def process_key_definitions(self, json_data):
        key_configs = {}
        global_key_config = self.process_globals(json_data)
        for app, configs in json_data["applications"].items():
            key_configs[app] = {}
            for key, config in configs.items():
                key_sequences, color_array, description, application, action, folder = self.get_config_items(config)
                if folder and folder not in json_data["folders"]:
                    print(
                        f"Error: Folder '{folder}' not found. Disabling key binding.")
                    key_sequences, color_array, description, application, action, folder = (
                        (), (0, 0, 0), '', '', '', '')
                key_configs[app][int(key)] = (key_sequences, color_array, description, application, action, folder)
            for key, config in global_key_config.items():
                if key not in key_configs[app]:
                    key_configs[app][key] = config
        return key_configs


    def process_folders(self, json_data):
        folders = {}
        global_key_config = self.process_globals(json_data)
        for folder_name, folder_configs in json_data["folders"].items():
            folders[folder_name] = {}
            close_folder_found = False
            for key, config in folder_configs.items():
                key_sequences, color_array, description, application, action, folder = self.get_config_items(config)
                if action == "close_folder":
                    close_folder_found = True
                folders[folder_name][int(key)] = (key_sequences, color_array, description, application, action, folder)
            if not close_folder_found:
                raise ValueError(
                    f"Error: Folder '{folder_name}' does not have a 'close_folder' action defined.")
            for key, config in global_key_config.items():
                if key not in folders[folder_name]:
                    folders[folder_name][key] = config
        return folders


    def read_key_configs(self, json_filename):
        with open(json_filename, 'r') as json_file:
            json_data = json.load(json_file)
        key_configs = self.process_key_definitions(json_data)
        folders = self.process_folders(json_data)
        global_config = self.process_globals(json_data)
        urls = self.process_urls(json_data)
        return key_configs, folders, global_config, urls


if __name__ == "__main__":
    controller = KeyController()
    try:
        controller.run()
    except KeyboardInterrupt:
        # turn off all the LEDs when the program is interrupted
        for key in controller.keys:
            key.led_off()
