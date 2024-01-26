# DIY Streamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0
# last changed: 01-19-24
# https://github.com/LennartHennigs/DIYStreamDeck

import time
import json
import usb_hid
import usb_cdc
from rgbkeypad import RgbKeypad
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
import board


class KeyController:
    JSON_FILE = "key_def.json"
    # https://docs.circuitpython.org/projects/hid/en/latest/_modules/adafruit_hid/keycode.html

    # mapping for the keycodes
    KEYCODE_MAPPING = {name: getattr(Keycode, name) for name in dir(
        Keycode) if not name.startswith("__")}

    # mapping for rotating the keys
    CW = [12, 8, 4, 0, 13, 9, 5, 1, 14, 10, 6, 2, 15, 11, 7, 3]
    CCW = [3, 7, 11, 15, 2, 6, 10, 14, 1, 5, 9, 13, 0, 4, 8, 12]


    # initialize the key controller
    def __init__(self, verbose=False):
        # initialize the keypad and keyboard
        self.keypad = RgbKeypad()
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.keys = self.keypad.keys
        # load and process the json file
        self.json = self.parse_json(self.JSON_FILE)
        self.global_config = self.process_global_section(self.json)
        self.apps = self.process_app_section(self.json)
        self.folders = self.process_folder_section(self.json)
        self.urls = self.process_url_section(self.json)
        self.current_config = self.apps.get("_otherwise", {})
        # rotate the keys if needed
        self.rotate = self.json["settings"]["rotate"].upper() if "rotate" in self.json.get("settings", {}) else ''
        self.current_config = self.rotate_keys_if_needed()
        # default settings
        self.verbose = verbose
        self.autoclose_current_folder = False
        self.folder_stack = [] 
        #  load the key layout
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
    def perform_folder_action(self, folder):
        self.open_folder(folder)
        return False


    # handle the key press
    def perform_plugin_action(self, action):
        self.send_plugin_command(*action)


    # handle the key press
    def perform_app_action(self, app):
        self.send_application_name(app)


    # handle the key press
    def perform_key_sequence_action(self, keys, pressedUntilReleased, pressedColor, key):
        self.handle_key_sequences(keys, pressedUntilReleased)
        if pressedColor:
            key.set_led(*pressedColor)


    # close the current folder if needed
    def close_folder_if_needed(self, someAction, action):
        if (someAction and self.autoclose_current_folder) or action == 'close_folder':
            self.close_folder()


    # handle the key press
    def key_press_action(self, key):
        if key.number not in self.current_config:
            return
        key_def = self.current_config[key.number]
        action = key_def.get('action')
        folder = key_def.get('folder')
        app = key_def.get('application')
        keys = key_def.get('key_sequences')
        pressedUntilReleased = key_def.get('pressedUntilReleased')
        pressedColor = key_def.get('pressedColor')
        # turn off the LED
        key.led_off()
        someAction = True
        # process the action
        if folder:
            someAction = self.perform_folder_action(folder)
        elif isinstance(action, tuple):
            self.perform_plugin_action(action)
        elif app:
            self.perform_app_action(app)
        elif keys:
            self.perform_key_sequence_action(keys, pressedUntilReleased, pressedColor, key)

        self.close_folder_if_needed(someAction, action)
        

    # handle the key release
    def key_release_action(self, key):
        if key.number not in self.current_config:
            return
        key_def = self.current_config[key.number]
        keys = key_def.get('key_sequences')
        color = key_def.get('color')
        pressedUntilReleased = key_def.get('pressedUntilReleased')
        toggleColor = key_def.get('toggleColor')

        if keys:
            self.keyboard.release_all()
            if toggleColor:
                temp = color;
                color = toggleColor;
                self.current_config[key.number]['color'] = toggleColor;
                self.current_config[key.number]['toggleColor'] = temp;
            key.set_led(*color) 


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
                color = self.current_config[key.number]['color']
                key.set_led(*color);
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
            return False


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
            'application': application,
            'action': self.convert_action_string(config.get('action', '')),
            'folder': config.get('folder', ''),

            'color': self.color_string_to_tuple(config.get('color', '')),
            'toggleColor': self.color_string_to_tuple(config.get('toggleColor', '')),
            'pressedColor': self.color_string_to_tuple(config.get('pressedColor', '')),

            'description': config.get('description', ''),
            'pressedUntilReleased': config.get('pressedUntilReleased', '')
        }

    
    # load the config for the urls
    def process_url_section(self, json_data):
        urls = {}
        if "urls" in json_data:
            for url, configs in json_data["urls"].items():
                urls[url] = {}
                for key, config in configs.items():
                    config_items = self.get_config_items(config)
                    urls[url][int(key)] = config_items
        return urls
    

    # load the config for the global section
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


    # load the config for a single application
    def process_config(self, config, json_data, app, app_config):
        containsToggle = False
        for key, value in config.items():
            if key == "ignore_default":
                continue
            config_items = self.get_config_items(value)
            # check if the folder exists
            if config_items['folder'] and config_items['folder'] not in json_data["folders"]:
                print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
                config_items['key_sequences'] = ()
            else:                     
                app_config[app][int(key)] = config_items
            # check if toggleColor is set
            if 'toggleColor' in config_items and config_items['toggleColor']:
                containsToggle = True

        # add the default config if needed
        ignore_default = config.get("ignore_default", "false").lower() == "true"
        if not ignore_default:
            self.add_global_config(app_config[app]);
        app_config[app]['containsToggle'] = containsToggle
        return app_config


    # load the config for a single application
    def load_single_app_config(self, app, config, json_data):
        # check if this is an alias
        if 'alias_of' in config:
            if config['alias_of'] in json_data["applications"]:
                config = json_data["applications"][config['alias_of']]
            else:
                print(f"Error: Alias '{config['alias_of']}' not found in applications.")
                return None
        # process the config
        app_config = {app: {}}
        self.process_config(config, json_data, app, app_config)
        return app_config[app]


    # load the config for all applications
    def process_app_section(self, json_data):
        app_config = {}
        for app, config in json_data["applications"].items():
            single_app_config = self.load_single_app_config(app, config, json_data)
            if single_app_config is not None:
                app_config[app] = single_app_config
        return app_config


    # load the config for all folders
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


    # add the global config to the app config
    def add_global_config(self, config):
        for key, value in self.global_config.items():
            if key not in config:
                config[key] = value


    # parse the json file
    def parse_json(self, json_filename): 
        with open(json_filename, 'r') as json_file:
            return json.load(json_file)


    # process the rotate serial command
    def process_rotate(self, serial_str):
        self.rotate = serial_str[8:]
        self.current_config = self.rotate_keys_if_needed()
        self.update_keys()


    # process the terminated serial command
    def process_terminated(self, serial_str):
        app_name = serial_str[12:]
        if app_name in self.json["applications"] and self.apps[app_name].get('containsToggle', False):
            self.apps[app_name] = self.load_single_app_config(app_name, self.json["applications"][app_name], self.json)


    #  process the app serial command
    def process_app(self, serial_str):
        app_name, url = self.parse_app_name_and_url(serial_str[5:])
        if url in self.urls:
            self.current_config = self.urls[url]
        else:
            self.current_config = self.apps.get(app_name, self.apps.get("_otherwise", {}))
        self.current_config = self.rotate_keys_if_needed()
        self.update_keys()


    # parse the app name and url
    def parse_app_name_and_url(self, serial_str):
        split_app_name = serial_str.split(" (", 1)
        app_name = split_app_name[0]
        url = split_app_name[1].rstrip(')') if len(split_app_name) > 1 else None
        return app_name, url


    # process the ping serial command
    def process_ping(self):
        return


    # process the serial string
    def process_serial_str(self, serial_str):
            # process the ping command
        if serial_str is ".":
            self.process_ping();
        if serial_str.startswith("Rotate: "):
            self.process_rotate(serial_str)
        elif serial_str.startswith("Terminated: "):
            self.process_terminated(serial_str)
        elif serial_str.startswith("App: "):
            self.process_app(serial_str)


    # main loop
    def run(self):
        while True:
            serial_str = self.read_serial_line()
            if serial_str is not None:
                self.process_serial_str(serial_str)
            else:
                time.sleep(0.1)
                self.keypad.update()


# main program
if __name__ == "__main__":
    controller = KeyController()
    try:
        controller.run()
    except KeyboardInterrupt:
        # release all keys and turn off the LEDs
        controller.keyboard.release_all()
        for key in controller.keys:
            key.led_off()


