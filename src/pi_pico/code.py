# DIY Streamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0
# last changed: 23-11-04
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
        self.verbose = verbose
        self.keypad = RgbKeypad()
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.keys = self.keypad.keys
        self.autoclose_current_folder = False

        self.json = self.parse_json(self.JSON_FILE)
        self.global_config = self.process_global_section(self.json)
        self.apps = self.process_app_section(self.json)
        self.folders = self.process_folder_section(self.json)
        self.urls = self.process_url_section(self.json)

        self.current_config = self.apps.get("_otherwise", {})
        self.folder_stack = [] 
        self.update_keys()

    
    def open_folder(self, folder):        
        if folder in self.folders:
            self.folder_stack.append(self.current_config)
            self.current_config= self.folders[folder]
            self.autoclose_current_folder = self.current_config.get('autoclose', True)
            self.update_keys()


    def close_folder(self):
        if not self.folder_stack:
            return
        self.current_config = self.folder_stack.pop()
        self.update_keys()


    def key_action(self, key):
        if key.number not in self.current_config:
            return
        key_def = self.current_config[key.number]

        action = key_def.get('action')
        folder = key_def.get('folder')
        app = key_def.get('application')
        keys = key_def.get('key_sequences')
        someAction = True
        #  open a folder?
        if folder:
            self.open_folder(folder)
            someAction = False
        # is the action is a plugin command
        elif isinstance(action, tuple):
            self.send_plugin_command(*action)
        # open an application?
        elif app:
            self.send_application_name(app)
        # handle the key sequences
        elif keys:
            self.handle_key_sequences(keys)
        # close the folder
        if (someAction and self.autoclose_current_folder) or action == 'close_folder':
            self.close_folder()      

            
    def handle_key_sequences(self, key_sequences):
        for item in key_sequences:
            # is it a delay?
            if isinstance(item, float):
                self.keyboard.release_all()
                time.sleep(item)
            # is it a key sequence?
            elif isinstance(item, tuple):
                self.keyboard.press(*item)
            # is it a single key?
            else:
                self.keyboard.press(item)
        # release all keys
        time.sleep(0.025);
        self.keyboard.release_all()
        self.update_keys()


    def update_keys(self):
        for key in self.keys:
            # Turn off the key LED by default
            key.led_off()
            # Set default no-op handlers
            self.keypad.on_press(key, lambda _, key=key: None)
            self.keypad.on_release(key, lambda _, key=key: None)
            # If there's a specific configuration for this key, update the LED and set event handlers
            if key.number in self.current_config:
                key.set_led(*self.current_config[key.number]['color']);
                # Set the actual key event handlers
                self.keypad.on_press(key, lambda key=key: key.led_off())
                self.keypad.on_release(key, lambda key=key: self.key_action(key))


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
            serial_str = self.read_serial_line()
            if serial_str is not None:
                # Split the app_name string on the first occurrence of " ("
                split_app_name = serial_str.split(" (", 1)
                # The first part is always the app name
                app_name = split_app_name[0]
                # The second part is the details, if they exist
                url = None
                if len(split_app_name) > 1:
                    # Remove the trailing ")" from the details
                    url = split_app_name[1].rstrip(')')
                # Check if there is a keyboard definition for the URL
                if url in self.urls:
                    self.current_config = self.urls[url]
                else:
                    self.current_config = self.apps.get(app_name, self.apps.get("_otherwise", {}))
                self.update_keys()
            else:
                time.sleep(0.1)
                self.keypad.update()


    def keycode_string_to_tuple (self, keycode_string):
        keycode_list = keycode_string.split('+')
        keycodes = []
        for key in keycode_list:
            if key.upper() == "CMD":
                key = "GUI"
            if key not in self.KEYCODE_MAPPING:
                raise ValueError(
                    f"Unknown keycode constant: {key} in '{keycode_string}'")
            keycodes.append(self.KEYCODE_MAPPING[key])
        return tuple(keycodes)


    def color_string_to_tuple(self, color_string):
        if color_string.startswith("#"):
            return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
        else:
            return (0, 0, 0)


    def convert_action_string(self, action):
        if action and '.' in action:
            return tuple(action.split('.',1))
        else:
            return action


    def convert_value(self, value):
        if isinstance(value, str):
            return self.keycode_string_to_tuple (value)
        else:
            return value


    def get_config_items(self, config):
        key_sequence = config.get('key_sequence', [])
        key_sequences = tuple(self.convert_value(v) for v in key_sequence) if isinstance(
            key_sequence, list) else self.keycode_string_to_tuple (key_sequence)
        return {
            'key_sequences': key_sequences,
            'color': self.color_string_to_tuple(config.get('color', '')),
            'description': config.get('description', ''),
            'application': config.get('application', ''),
            'action': self.convert_action_string(config.get('action', '')),
            'folder': config.get('folder', '')
        }


    def process_url_section(self, json_data):
        urls = {}
        if "urls" in json_data:
            for url, configs in json_data["urls"].items():
                urls[url] = {}
                for key, config in configs.items():
                    config_items = self.get_config_items(config)
                    urls[url][int(key)] = config_items
        return urls
    

    def process_global_section(self, json_data):
        global_config = {}
        if "global" in json_data:
            for key, config in json_data["global"].items():
                config_items = self.get_config_items(config)
                if config_items['folder'] and config_items['folder'] not in json_data["folders"]:
                    print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
                else:                 
                    global_config[int(key)] = config_items               
        return global_config


    def process_app_section(self, json_data):
        app_config = {}
        for app, config in json_data["applications"].items():
            app_config[app] = {}
            for key, value in config.items():
                if key == "ignore_globals":
                    continue
                config_items = self.get_config_items(value)
                if config_items['folder'] and config_items['folder'] not in json_data["folders"]:
                    print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
                    config_items['key_sequences'] = ()
                else:                     
                    app_config[app][int(key)] = config_items
            ignore_globals = config.get("ignore_globals", "false").lower() == "true"
            if not ignore_globals:
                self.add_global_config(app_config[app]);
        return app_config


    def process_folder_section(self, json_data):
        folder_config = {}
        for folder, config in json_data["folders"].items():
            folder_config[folder] = {}
            folder_config[folder]['autoclose'] = config.get("autoclose", "true").lower() == "true"
            close_folder_found = False
            for key, value in config.items():
                if key in ["ignore_globals", "autoclose"]:
                    continue
                config_items = self.get_config_items(value)
                folder_config[folder][int(key)] = config_items
                if config_items['action'] == "close_folder":
                    close_folder_found = True
            if not close_folder_found and not folder_config[folder]['autoclose']:
                raise ValueError(f"Error: Folder '{folder}' does not have a 'close_folder' action defined.")
            ignore_globals = config.get("ignore_globals", "false").lower() == "true"
            if not ignore_globals:
                self.add_global_config(folder_config[folder]);
        return folder_config


    def add_global_config(self, config):
        for key, value in self.global_config.items():
            if key not in config:
                config[key] = value


    def parse_json(self, json_filename): 
        with open(json_filename, 'r') as json_file:
            return json.load(json_file)


if __name__ == "__main__":
    controller = KeyController()
    try:
        controller.run()
    except KeyboardInterrupt:
        # turn off all the LEDs when the program is interrupted
        for key in controller.keys:
            key.led_off()

