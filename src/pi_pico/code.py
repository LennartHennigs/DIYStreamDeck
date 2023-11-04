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
        self.autoclose_current_folder = False
        self.urls = {}
        self.global_config = {}
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.key_configs, self.folders, self.global_config, self.urls = self.read_key_configs(self.JSON_FILE)
        self.current_config = self.key_configs.get("_otherwise", {})
        self.usb_serial = usb_cdc.console
        self.update_keys()
        self.folder_open = False
        self.active_app = None
        self.last_key_config = None
        self.folder_stack = [] 

    
    def open_folder(self, folder_name):        
        if folder_name in self.folders:
            self.folder_stack.append(self.current_config)
            self.folder_open = True
            self.current_config= self.folders[folder_name]
            self.autoclose_current_folder = self.current_config.get('autoclose', True)
            self.update_keys()


    def close_folder(self):
        if not self.folder_stack:
            return
        self.current_config = self.folder_stack.pop()
        # update the keys
        self.update_keys()


    def key_action(self, key, press=True):
        # check if the key is in the current key config
        if key.number not in self.current_config:
            return
        # get the key config for the key
        key_def = self.current_config[key.number]
        # key is pressed
        if press:
            key.led_off()
        # key is released
        else:
            someAction = False
            #  open a folder?
            if key_def.get('folder'):
                self.open_folder(key_def.get('folder'))
            # is the action is a plugin command
            elif isinstance(key_def.get('action'), tuple):
                self.send_plugin_command(*key_def.get('action'))
                someAction = True
            # open an application?
            elif key_def.get('application'):
                self.send_application_name(key_def.get('application'))
                someAction = True
            # handle the key sequences
            elif key_def.get('key_sequences'):
                self.handle_key_sequences(key_def.get('key_sequences'))
                someAction = True
            # close the folder
            if (someAction and self.autoclose_current_folder) or key_def.get('action') == 'close_folder':
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
        time.sleep(0.05);
        self.keyboard.release_all()


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
                self.keypad.on_press(key, self.key_action)
                self.keypad.on_release(key, lambda key=key: self.key_action(key, press=False))


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
            # print(f"Sent to Mac: Launch: {app_name}")
        except Exception as e:
            # print(f"Could not launch {app_name}: {e}\n")
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
                    self.current_config = self.urls[url]
                else:
                    self.current_config = self.key_configs.get(app_name, self.key_configs.get("_otherwise", {}))
                self.update_keys()
            else:
                time.sleep(0.1)
                self.keypad.update()


    def keycode_string_to_tupel(self, keycode_string):
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
        else:
            return (0, 0, 0)


    def convert_value(self, value):
        if isinstance(value, str):
            return self.keycode_string_to_tupel(value)
        else:
            return value


    def get_config_items(self, config):
        key_sequence = config.get('key_sequence', [])
        key_sequences = tuple(self.convert_value(v) for v in key_sequence) if isinstance(
            key_sequence, list) else self.keycode_string_to_tupel(key_sequence)
        color_array = self.convert_color_string(config.get('color', ''))
        description = config.get('description', '')
        application = config.get('application', '')
        action = config.get('action', '')
        if action and '.' in action:
            action = tuple(action.split('.',1))
        folder = config.get('folder', '')
        return {
            'key_sequences': key_sequences,
            'color': color_array,
            'description': description,
            'application': application,
            'action': action,
            'folder': folder
        }


    def process_urls(self, json_data):
        urls = {}
        if "urls" in json_data:
            for url, configs in json_data["urls"].items():
                print(url)
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


    def process_app_section(self, json_data, global_config):
        key_configs = {}
        for app, configs in json_data["applications"].items():
            # print(f"Application {app} loaded.")
            key_configs[app] = {}
            ignore_globals = configs.get("ignore_globals", "false").lower() == "true"
            for key, config in configs.items():
                if key == "ignore_globals":
                    continue
                config_items = self.get_config_items(config)
                if config_items['folder'] and config_items['folder'] not in json_data["folders"]:
                    print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
                    config_items['key_sequences'] = ()
                else:                     
                    key_configs[app][int(key)] = config_items
            if not ignore_globals:
                for key, config in global_config.items():
                    if int(key) not in key_configs[app]:
                        key_configs[app][int(key)] = config
        return key_configs


    def process_folder_section(self, json_data, global_config):
        folders = {}
        for folder_name, folder_config in json_data["folders"].items():
            folders[folder_name] = {}
            # Check if the folder has an autoclose setting
            autoclose = folder_config.get("autoclose", "true").lower() == "true"
            folders[folder_name]['autoclose'] = autoclose
            # Check if the folder has an ignore_globals setting
            ignore_globals = folder_config.get("ignore_globals", "false").lower() == "true"
            close_folder_found = False
            # Process the keys in the folder

            for key, config in folder_config.items():
                # Skip the special settings
                if key in ["ignore_globals", "autoclose"]:
                    continue
                # Process the key config
                config_items = self.get_config_items(config)
                if config_items['action'] == "close_folder":
                    close_folder_found = True
                folders[folder_name][int(key)] = config_items
            if not close_folder_found:
                raise ValueError(f"Error: Folder '{folder_name}' does not have a 'close_folder' action defined.")
            # Add the global key configs to the folder definition if they are not ignored
            if not ignore_globals:
                for key, config in global_config.items():
                    if key not in folders[folder_name]:
                        folders[folder_name][key] = config

        return folders

    
    def read_key_configs(self, json_filename):
        with open(json_filename, 'r') as json_file:
            json_data = json.load(json_file)
        global_config = self.process_global_section(json_data)
        key_configs = self.process_app_section(json_data, global_config)
        folders = self.process_folder_section(json_data, global_config)
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

