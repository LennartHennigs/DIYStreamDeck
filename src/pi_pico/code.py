# DIY Streamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0
# last changed: 01-31-24
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

# Heartbeat and timeout configuration for the keypad firmware.
# The host sends heartbeat frames at roughly PICO_HEARTBEAT_INTERVAL seconds.
# If no heartbeat (or HELLO) is seen within PICO_HEARTBEAT_INTERVAL * PICO_TIMEOUT_MULTIPLIER
# the keypad will clear and unload itself.
PICO_HEARTBEAT_INTERVAL = 2
PICO_TIMEOUT_MULTIPLIER = 2
PICO_TIMEOUT_SECONDS = PICO_HEARTBEAT_INTERVAL * PICO_TIMEOUT_MULTIPLIER


class KeyController:
    JSON_FILE = "key_def.json"
    # https://docs.circuitpython.org/projects/hid/en/latest/_modules/adafruit_hid/keycode.html

    # mapping for the keycodes - will be initialized in __init__
    KEYCODE_MAPPING = None

    # mapping for rotating the keys
    CW = [12, 8, 4, 0, 13, 9, 5, 1, 14, 10, 6, 2, 15, 11, 7, 3]
    CCW = [3, 7, 11, 15, 2, 6, 10, 14, 1, 5, 9, 13, 0, 4, 8, 12]


    # initialize the key controller
    def __init__(self, verbose=False):
        # initialize keycode mapping (once per class, not per instance)
        if KeyController.KEYCODE_MAPPING is None:
            KeyController.KEYCODE_MAPPING = {name: getattr(Keycode, name) for name in dir(
                Keycode) if not name.startswith("__")}
        
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

        # rotate the keys if needed (robust to missing settings)
        rotate_setting = self.json.get("settings", {}).get("rotate", "")
        rotate_upper = rotate_setting.upper() if isinstance(rotate_setting, str) else ''
        if rotate_upper not in ("CW", "CCW", ""):
            print(f"Warning: Invalid rotation setting '{rotate_setting}', ignoring")
            rotate_upper = ''
        self.rotate = rotate_upper
        self.current_config = self.rotate_keys_if_needed()

        # default settings
        self.verbose = verbose
        self.autoclose_current_folder = False
        self.folder_stack = []

        # load the key layout
        self.update_keys()

        # Heartbeat / timeout handling
        # Keep a timestamp of the last received heartbeat (or HELLO)
        self.last_heartbeat = time.time()
        # If True the keypad has been unloaded due to timeout or BYE
        self.unloaded = False


    # open a folder and display the key layout
    def open_folder(self, folder):
        if folder in self.folders:
            self.folder_stack.append(self.current_config)
            self.current_config = self.folders[folder]
            self.current_config = self.rotate_keys_if_needed()
            self.autoclose_current_folder = self.current_config.get('autoclose', True)
            self.update_keys()


    # close the current folder if needed
    def close_folder_if_needed(self, some_action, action):
        if (some_action and self.autoclose_current_folder) or action == 'close_folder':
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
        pressedUntilReleased = key_def.get('pressedUntilReleased')
        pressedColor = key_def.get('pressedColor')
        key.led_off()
        some_action = True
        if folder:
            self.open_folder(folder)
            some_action = False
        elif isinstance(action, tuple):
            self.send_plugin_command(*action)
        elif app:
            self.send_application_name(app)
        elif keys:
            self.handle_key_sequences(keys, pressedUntilReleased)
        if pressedColor and not folder:
            key.set_led(*pressedColor)
        # close the folder if needed
        self.close_folder_if_needed(some_action, action)
        

    # handle the key release
    def key_release_action(self, key):
        if key.number not in self.current_config:
            return
        key_def = self.current_config[key.number]
        keys = key_def.get('key_sequences')
        color = key_def.get('color')
        pressedUntilReleased = key_def.get('pressedUntilReleased')
        toggleColor = key_def.get('toggleColor')
        # process the action
        if keys:
            self.keyboard.release_all()
            if toggleColor:
                temp = color
                color = toggleColor
                self.current_config[key.number]['color'] = toggleColor
                self.current_config[key.number]['toggleColor'] = temp
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
            time.sleep(0.025)
            self.keyboard.release_all()


    # update the key layout
    def update_keys(self):
        for key in self.keys:
            # is there a key definition for this key?
            if key.number in self.current_config:
                color = self.current_config[key.number]['color']
                if color:
                    key.set_led(*color)
                else:
                    raise ValueError(f"Error: Color not defined for key {key.number}.")
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
            if self.verbose:
                print(f"Serial write error: {e}")


    # send the plugin command via serial
    def send_plugin_command(self, plugin, command):
        # command may include a parameter, e.g. "toggle 'Lamp Name'" — intentional, matches Mac parser
        try:
            usb_cdc.console.write(f"Run: {plugin}.{command}\n".encode('utf-8'))
        except Exception as e:
            if self.verbose:
                print(f"Serial write error: {e}")


    # rotate the keys if needed
    def rotate_keys_if_needed (self):
        if self.rotate == "CW":
            return {i: self.current_config[cw] for i, cw in enumerate(self.CW) if cw in self.current_config}
        elif self.rotate == "CCW":
            return {i: self.current_config[ccw] for i, ccw in enumerate(self.CCW) if ccw in self.current_config}
        return self.current_config
        

    # convert the keycodes to tuples if needed
    def keycode_string_to_tuple (self, keycode_string):
        if not keycode_string or not keycode_string.strip():
            raise ValueError("Empty key_sequence string")
        keycode_list = keycode_string.split('+')
        keycodes = []
        for key in keycode_list:
            if key.upper() == "CMD":
                key = "GUI"
            if key not in self.KEYCODE_MAPPING:
                raise ValueError(f"Unknown keycode constant: {key} in '{keycode_string}'")
            keycodes.append(self.KEYCODE_MAPPING[key])
        return tuple(keycodes)


    # convert the color string to a tuple if needed
    def color_string_to_tuple(self, color_string):
        if not color_string or not isinstance(color_string, str):
            return None
        if color_string.startswith("#"):
            try:
                return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
            except ValueError:
                raise ValueError(f"Invalid hex color: {color_string!r}")
        return None


    # parse a bool from a config value that may be a native bool or string "true"/"false"
    def parse_bool_from_config(self, value, default=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return default


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
        # get the key sequences
        key_sequence = config.get('key_sequence', [])
        key_sequences = tuple(self.convert_value(v) for v in key_sequence) if isinstance(
            key_sequence, list) else self.keycode_string_to_tuple (key_sequence)
        # return the config items
        return {
            'key_sequences': key_sequences,
            'application': config.get('application', ''),
            'action': self.convert_action_string(config.get('action', '')),
            'folder': config.get('folder', ''),

            'color': self.color_string_to_tuple(config.get('color', '')),
            'toggleColor': self.color_string_to_tuple(config.get('toggleColor', '')),
            'pressedColor': self.color_string_to_tuple(config.get('pressedColor', '')),

            'description': config.get('description', ''),
            'pressedUntilReleased': config.get('pressedUntilReleased', False)
        }

    
    # load the config for the urls
    def process_url_section(self, json_data):
        urls = {}
        if "urls" in json_data:
            for url, configs in json_data["urls"].items():
                urls[url] = {}
                for key, config in configs.items():
                    config_items = self.get_config_items(config)
                    key_num = self._validate_key_number(key)
                    if key_num is not None:
                        urls[url][key_num] = config_items
                self.add_global_config(urls[url])
        return urls
    

    # load the config for the global section
    def process_global_section(self, json_data):
        global_config = {}
        if "applications" in json_data and "_default" in json_data["applications"]:
            for key, config in json_data["applications"]["_default"].items():
                config_items = self.get_config_items(config)
                if config_items['folder'] and config_items['folder'] not in json_data.get("folders", {}):
                    print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
                else:
                    key_num = self._validate_key_number(key)
                    if key_num is not None:
                        global_config[key_num] = config_items
        return global_config


    # load the config for a single application
    def process_config(self, config, json_data, app, app_config):
        containsToggle = False
        for key, value in config.items():
            if key == "ignore_default":
                continue
            config_items = self.get_config_items(value)
            # check if the folder exists
            if config_items['folder'] and config_items['folder'] not in json_data.get("folders", {}):
                print(f"Error: Folder '{config_items['folder']}' not found. Disabling key binding.")
            else:
                key_num = self._validate_key_number(key)
                if key_num is not None:
                    app_config[app][key_num] = config_items
            # check if toggleColor is set
            if 'toggleColor' in config_items and config_items['toggleColor']:
                containsToggle = True
        # add the default config if needed
        ignore_default = self.parse_bool_from_config(config.get("ignore_default", False))
        if not ignore_default:
            self.add_global_config(app_config[app])
        app_config[app]['containsToggle'] = containsToggle
        return app_config


    # load the config for a single application
    def load_single_app_config(self, app, config, json_data):
        # check if this is an alias
        if 'alias_of' in config:
            alias_target = config['alias_of']
            if alias_target not in json_data["applications"]:
                print(f"Error: Alias '{alias_target}' not found in applications.")
                return None
            resolved = json_data["applications"][alias_target]
            # Hard limit: chained aliases are not supported
            if 'alias_of' in resolved:
                print(f"Error: Chained alias not supported: "
                      f"'{app}' -> '{alias_target}' -> '{resolved['alias_of']}'")
                return None
            config = resolved
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
        for folder, config in json_data.get("folders", {}).items():
            folder_config[folder] = {}
            folder_config[folder]['autoclose'] = self.parse_bool_from_config(config.get("autoclose", True))
            close_folder_found = False
            for key, value in config.items():
                if key in ["ignore_default", "autoclose"]:
                    continue
                config_items = self.get_config_items(value)
                key_num = self._validate_key_number(key)
                if key_num is not None:
                    folder_config[folder][key_num] = config_items
                if config_items['action'] == "close_folder":
                    close_folder_found = True
            if not close_folder_found and not folder_config[folder]['autoclose']:
                raise ValueError(f"Error: Folder '{folder}' does not have a 'close_folder' action defined.")
            ignore_default = self.parse_bool_from_config(config.get("ignore_default", False))
            if not ignore_default:
                self.add_global_config(folder_config[folder])
        return folder_config


    # add the global config to the app config
    def add_global_config(self, config):
        for key, value in self.global_config.items():
            if key not in config:
                config[key] = value


    # validate that a key number string is in the valid range 0-15
    def _validate_key_number(self, key_str):
        try:
            key_num = int(key_str)
        except (ValueError, TypeError):
            print(f"Warning: Key '{key_str}' is not a valid number, ignoring")
            return None
        if key_num < 0 or key_num > 15:
            print(f"Warning: Key number {key_num} out of range (0-15), ignoring")
            return None
        return key_num


    # parse the json file
    def parse_json(self, json_filename):
        try:
            with open(json_filename, 'r') as json_file:
                return json.load(json_file)
        except OSError as e:
            raise type(e)(f"Config file '{json_filename}' not found") from None
        except ValueError as e:
            raise ValueError(f"Invalid JSON in '{json_filename}': {e}") from None


    # process the rotate serial command
    def process_rotate(self, serial_str):
        value = serial_str[8:].upper()
        if value not in ("CW", "CCW", ""):
            print(f"Warning: Invalid rotation value '{value}', ignoring")
            return
        self.rotate = value
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


    # Clear the keypad LEDs and handlers (leave no active config)
    def clear_keypad(self):
        # release any pressed keys and turn off LEDs
        try:
            self.keyboard.release_all()
        except Exception:
            pass
        for key in self.keys:
            try:
                key.led_off()
            except Exception:
                pass
            # detach handlers to prevent accidental actions
            try:
                self.keypad.on_press(key, lambda _, key=key: None)
                self.keypad.on_release(key, lambda _, key=key: None)
            except Exception:
                pass
        # empty current config
        self.current_config = {}


    # Load the basic/default config (the _otherwise app)
    def load_basic_config(self):
        self.current_config = self.apps.get("_otherwise", {})
        self.current_config = self.rotate_keys_if_needed()
        # re-apply key handlers and colors
        self.update_keys()
        self.unloaded = False


    # Unload the keypad: clear and mark unloaded so timeout actions are idempotent
    def unload_keypad(self):
        if self.unloaded:
            return
        self.unloaded = True
        self.clear_keypad()


    # process the serial string
    def process_serial_str(self, serial_str):
        # Heartbeat frame from host
        if serial_str == "HB":
            # update last seen heartbeat timestamp
            self.last_heartbeat = time.time()
            return

        # HELLO: host started -> clear keypad then load basic config
        if serial_str.startswith("HELLO"):
            self.clear_keypad()
            self.load_basic_config()
            self.last_heartbeat = time.time()
            return

        # BYE: host shutting down -> clear and mark unloaded
        if serial_str.startswith("BYE"):
            self.clear_keypad()
            self.unloaded = True
            return

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
                # No incoming serial - throttle idle CPU usage
                time.sleep(0.1)
            self.keypad.update()  # always poll key state, even after processing serial

            # Check for heartbeat timeout. If we haven't seen a heartbeat (or HELLO)
            # within PICO_TIMEOUT_SECONDS, clear and unload the keypad.
            try:
                if (not self.unloaded) and (time.time() - self.last_heartbeat > PICO_TIMEOUT_SECONDS):
                    # perform unload on timeout
                    self.unload_keypad()
            except Exception as e:
                if self.verbose:
                    print(f"Heartbeat check error: {e}")


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

