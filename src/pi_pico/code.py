# DIY Streamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0
# last changed: 12-11-23
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

    # mapping for rotating the keys
    CW = [12, 8, 4, 0, 13, 9, 5, 1, 14, 10, 6, 2, 15, 11, 7, 3]
    CCW = [3, 7, 11, 15, 2, 6, 10, 14, 1, 5, 9, 13, 0, 4, 8, 12]

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
        self.rotate = self.json["settings"]["rotate"].upper() if "rotate" in self.json.get("settings", {}) else ''
        self.current_config = self.rotate_keys_if_needed()                    

        self.folder_stack = [] 
        self.update_keys()


    # open a folder and display the key layout
    def open_folder(self, folder):        
        if folder in self.folders:
            self.folder_stack.append(self.current_config)
            self.current_config = self.folders[folder]
            self.current_config = self.rotate_keys_if_needed()                    
            self.autoclose_current_folder = self.current_config.get('autoclose', True)
            self.update_keys()


    # close the current folder and display previous key layout
    def close_folder(self):
        if not self.folder_stack:
            return
        self.current_config = self.folder_stack.pop()
        self.update_keys()


    # handle the key press
    def key_press_action(self, key):
        if key.number not in self.current_config:
            return
        key_def = self.current_config[key.number]

        action = key_def.get('action')
        folder = key_def.get('folder')
        app = key_def.get('application')
        keys = key_def.get('key_sequences')
        pressedUntilReleased = key_def.get('pressedUntilReleased', False)

        # turn off the LED
        key.led_off()

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
            self.handle_key_sequences(keys, pressedUntilReleased)
            key.set_led(*self.current_config[key.number]['color']);
        # close the folder
        if (someAction and self.autoclose_current_folder) or action == 'close_folder':
            self.close_folder()      


    # handle the key release
    def key_release_action(self, key):
        if key.number not in self.current_config:
            return
        key_def = self.current_config[key.number]
        keys = key_def.get('key_sequences')
        pressedUntilReleased = key_def.get('pressedUntilReleased', False)

        if keys and pressedUntilReleased:
            self.keyboard.release_all()


    # handle the key sequences
    def handle_key_sequences(self, key_sequences, pressedUntilReleased):
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
        if not pressedUntilReleased:
            time.sleep(0.025);
            self.keyboard.release_all()


    # update the key layout
    def update_keys(self):
        for key in self.keys:
            # is there a key definition for this key?
            if key.number in self.current_config:
                key.set_led(*self.current_config[key.number]['color']);
                # set the key press and release handlers
                self.keypad.on_press(key, lambda key=key: self.key_press_action(key))
                self.keypad.on_release(key, lambda key=key: self.key_release_action(key))               
            # no key definition found
            else:            
                key.led_off()
                self.keypad.on_press(key, lambda _, key=key: None)
                self.keypad.on_release(key, lambda _, key=key: None)


    # read a line from the serial console
    def read_serial_line(self):
        if usb_cdc.console.in_waiting > 0:
            raw_data = usb_cdc.console.readline()
            try:
                return raw_data.decode("utf-8").strip()
            except UnicodeDecodeError:
                pass
        return None


    # send the application name via serial
    def send_application_name(self, app_name):
        try:
            usb_cdc.console.write(f"Launch: {app_name}\n".encode('utf-8'))
        except Exception as e:
            pass


    # send the plugin command via serial
    def send_plugin_command(self, plugin, command):
        try:
            usb_cdc.console.write(f"Run: {plugin}.{command}\n".encode('utf-8'))
        except Exception as e:
            pass


    # rotate the keys if needed
    def rotate_keys_if_needed (self):
        if self.rotate == "CW":
            return {i: self.current_config[cw] for i, cw in enumerate(self.CW) if cw in self.current_config}
        elif self.rotate == "CCW":
            return {i: self.current_config[ccw] for i, ccw in enumerate(self.CCW) if ccw in self.current_config}
        
        return self.current_config
        

# convert the keycodes to tuples if needed
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


    # convert the color string to a tuple if needed
    def color_string_to_tuple(self, color_string):
        if color_string.startswith("#"):
            return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
        else:
            return (0, 0, 0)


    # convert the action string to a tuple
    def convert_action_string(self, action):
        if action and '.' in action:
            return tuple(action.split('.',1))
        else:
            return action


    # convert the value to a tuple if needed
    def convert_value(self, value):
        if isinstance(value, str):
            return self.keycode_string_to_tuple (value)
        else:
            return value


    # get the config items
    def get_config_items(self, config):
        if 'alias_of' in config:
            config = config['alias_of']

        key_sequence = config.get('key_sequence', [])
        key_sequences = tuple(self.convert_value(v) for v in key_sequence) if isinstance(
            key_sequence, list) else self.keycode_string_to_tuple (key_sequence)
        
        application = config.get('application', '')
        if 'alias_of' in config:
            application = config['alias_of']

        return {
            'key_sequences': key_sequences,
            'color': self.color_string_to_tuple(config.get('color', '')),
            'description': config.get('description', ''),
            'application': application,
            'action': self.convert_action_string(config.get('action', '')),
            'folder': config.get('folder', ''),
            'pressedUntilReleased': config.get('pressedUntilReleased', '')
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
        if "applications" in json_data and "_default" in json_data["applications"]:
            for key, config in json_data["applications"]["_default"].items():
                config_items = self.get_config_items(config)
                if config_items['folder'] and config_items['folder'] not in json_data["folders"]:
                    print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
                else:                 
                    global_config[int(key)] = config_items               
        return global_config


    def process_config(self, config, json_data, app, app_config):
        for key, value in config.items():
            if key == "ignore_default":
                continue
            config_items = self.get_config_items(value)
            if config_items['folder'] and config_items['folder'] not in json_data["folders"]:
                print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
                config_items['key_sequences'] = ()
            else:                     
                app_config[app][int(key)] = config_items
        ignore_default = config.get("ignore_default", "false").lower() == "true"
        if not ignore_default:
            self.add_global_config(app_config[app]);
        return app_config


    def process_app_section(self, json_data):
        app_config = {}
        for app, config in json_data["applications"].items():
            app_config[app] = {}
            #  check if this is an alias
            if 'alias_of' in config:
                if config['alias_of'] in json_data["applications"]:
                    config = json_data["applications"][config['alias_of']]
                else:
                    print(f"Error: Alias '{config['alias_of']}' not found in applications.")
                    continue
            self.process_config(config, json_data, app, app_config)
        return app_config


    def process_folder_section(self, json_data):
        folder_config = {}
        for folder, config in json_data["folders"].items():
            folder_config[folder] = {}
            folder_config[folder]['autoclose'] = config.get("autoclose", "true").lower() == "true"
            close_folder_found = False
            for key, value in config.items():
                if key in ["ignore_default", "autoclose"]:
                    continue
                config_items = self.get_config_items(value)
                folder_config[folder][int(key)] = config_items
                if config_items['action'] == "close_folder":
                    close_folder_found = True
            if not close_folder_found and not folder_config[folder]['autoclose']:
                raise ValueError(f"Error: Folder '{folder}' does not have a 'close_folder' action defined.")
            ignore_default = config.get("ignore_default", "false").lower() == "true"
            if not ignore_default:
                self.add_global_config(folder_config[folder]);
        return folder_config


    def add_global_config(self, config):
        for key, value in self.global_config.items():
            if key not in config:
                config[key] = value


    def parse_json(self, json_filename): 
        with open(json_filename, 'r') as json_file:
            return json.load(json_file)


    # main loop
    def run(self):
        while True:
            serial_str = self.read_serial_line()
            # check if we have a serial command
            if serial_str is not None:
                if serial_str is ".":
                    continue
                # shall we rotate the keys?
                if serial_str.startswith("Rotate: "):
                    self.rotate = serial_str[8:]
                    self.current_config = self.rotate_keys_if_needed()                    
                    self.update_keys()
                # shall we launch an application?
                elif serial_str.startswith("App: "):
                    serial_str = serial_str[5:]
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

                    self.current_config = self.rotate_keys_if_needed()                    
                    self.update_keys()
                
            else:
                time.sleep(0.1)
                self.keypad.update()


if __name__ == "__main__":
    controller = KeyController()
    try:
        controller.run()
    except KeyboardInterrupt:
        # turn off all the LEDs when the program is interrupted
        for key in controller.keys:
            key.led_off()


