# DIY Streamdeck code for a Pi Pico - CircuitPython
# L. Hennigs and ChatGPT 4.0
# last changed: 2026-06-03
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

# Signal colors for `Claude: <color>` serial messages from the Mac (claude plugin).
# Dim values on purpose — 16 LEDs at full intensity are harsh. Yellow uses
# equal R and G so the hue matches `#FFFF00` in key_def.json (asymmetric
# dimming turns yellow orange). The color the Pico sets stays lit until
# an app switch, rotation, keypress, or a new Claude: line overrides it —
# the color IS the status signal, not just an animation.
FLASH_COLORS = {
    "green":  (0, 90, 0),
    "red":    (110, 0, 0),
    "yellow": (110, 110, 0),
}

# Predefined color names usable anywhere a "#RRGGBB" hex value is accepted
# (color / toggleColor / pressedColor). Full-brightness values, matching the
# hex colors already used in key_def.json — kept separate from the dimmed
# FLASH_COLORS above, which are status signals with a different purpose.
NAMED_COLORS = {
    "black":   (0, 0, 0),
    "white":   (255, 255, 255),
    "red":     (255, 0, 0),
    "green":   (0, 255, 0),
    "blue":    (0, 0, 255),
    "yellow":  (255, 255, 0),
    "orange":  (255, 165, 0),
    "cyan":    (0, 255, 255),
    "magenta": (255, 0, 255),
    "purple":  (128, 0, 128),
    "pink":    (255, 105, 180),
    "gray":    (128, 128, 128),
    "grey":    (128, 128, 128),
}


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
        # Must be first: config processing below reports errors via
        # send_output -> _serial_write, whose error handler reads self.verbose.
        self.verbose = verbose

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

        # rotate the keys if needed (robust to missing settings)
        rotate_setting = self.json.get("settings", {}).get("rotate", "")
        rotate_upper = rotate_setting.upper() if isinstance(rotate_setting, str) else ''
        if rotate_upper not in ("CW", "CCW", ""):
            print(f"Warning: Invalid rotation setting '{rotate_setting}', ignoring")
            rotate_upper = ''
        self.rotate = rotate_upper

        # default settings
        self.autoclose_current_folder = False
        self.folder_stack = []
        self._set_top_config(self.apps.get("_otherwise", {}))

        # Sticky signal state: holds the RGB tuple currently flood-filled as a
        # Claude Code status signal, or None when the real layout is showing.
        # update_keys() clears it — every repaint of the real layout is a
        # deliberate ack (app switch, rotate, HELLO, keypress, folder open/close).
        # A new `Claude:` line while one is active just overwrites it. Must be
        # set before the first update_keys() call below (which reads it).
        self._signal_color = None

        # load the key layout
        self.update_keys()

        # Heartbeat / timeout handling
        # Keep a timestamp of the last received heartbeat (or HELLO)
        self.last_heartbeat = time.monotonic()
        # If True the keypad has been unloaded due to timeout or BYE
        self.unloaded = False


    # open a folder and display the key layout
    def open_folder(self, folder):
        if folder in self.folders:
            self.folder_stack.append((self._unrotated_config, self.autoclose_current_folder))
            # read autoclose from the unrotated folder config — rotation drops
            # non-numeric keys like 'autoclose'
            self.autoclose_current_folder = self.folders[folder].get('autoclose', True)
            self._set_current_config(self.folders[folder])
            self.update_keys()


    # close the current folder if needed
    def close_folder_if_needed(self, some_action, action):
        if (some_action and self.autoclose_current_folder) or action == 'close_folder':
            if not self.folder_stack:
                return
            config, autoclose = self.folder_stack.pop()
            self.autoclose_current_folder = autoclose
            self._set_current_config(config)
            self.update_keys()


    # handle the key press
    def key_press_action(self, key):
        if key.number not in self.current_config:
            return
        # A keypress is a deliberate ack of any active Claude signal — repaint
        # the real layout first (update_keys() clears the sticky color),
        # otherwise the 15 non-pressed keys would keep showing the flood-fill.
        if self._signal_color is not None:
            self.update_keys()
        key_def = self.current_config[key.number]
        action = key_def.get('action')
        folder = key_def.get('folder')
        app = key_def.get('application')
        keys = key_def.get('key_sequences')
        text = key_def.get('string')
        string_delay = key_def.get('string_delay', 0.05)
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
        elif text:
            self.handle_string_key(text, string_delay)
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
        toggleColor = key_def.get('toggleColor')
        # process the action
        if keys:
            self.keyboard.release_all()
            if toggleColor:
                key_def['color'] = toggleColor
                key_def['toggleColor'] = color
                color = toggleColor
        # repaint the base color for every defined key — the press turned the
        # LED off (or set pressedColor), string/app/plugin keys included
        if color:
            key.set_led(*color)


    # handle the key sequences
    def handle_key_sequences(self, key_sequences, pressedUntilReleased):
        for item in key_sequences:
            # is it a delay? (only floats — top-level ints are keycodes from a
            # scalar key_sequence string; list delays are coerced to float at load)
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
        # Same heartbeat credit as handle_string_key — sequence delays block the loop.
        self.last_heartbeat = time.monotonic()


    # type a string with an optional per-character delay for slow apps
    def handle_string_key(self, text, delay=0.05):
        if not delay:
            self.layout.write(text)
        else:
            for char in text:
                self.layout.write(char)
                time.sleep(delay)
        # Typing blocks the main loop; credit back the self-inflicted delay so
        # a long string can't trip the heartbeat timeout and unload the keypad.
        self.last_heartbeat = time.monotonic()


    # update the key layout
    def update_keys(self):
        # Repainting the real layout acks any active Claude signal — drop the
        # sticky color so state matches what's actually on the LEDs. flash_all()
        # sets LEDs directly (not via update_keys), so the signal survives it.
        self._signal_color = None
        for key in self.keys:
            # is there a key definition for this key?
            if key.number in self.current_config:
                color = self.current_config[key.number]['color']
                if color:
                    key.set_led(*color)
                else:
                    # colors are validated at load time; never crash mid-session
                    key.led_off()
                    print(f"Warning: No color for key {key.number}, LED off")
                # set the key press and release handlers
                self.keypad.on_press(key, lambda key=key: self.key_press_action(key))
                self.keypad.on_release(key, lambda key=key: self.key_release_action(key))
            # no key definition found
            else:
                key.led_off()
                self.keypad.on_press(key, lambda _, key=key: None)
                self.keypad.on_release(key, lambda _, key=key: None)


    # flood-fill all LEDs with an RGB tuple and remember it as the sticky
    # signal color. The color persists until a deliberate ack — app switch,
    # rotate, HELLO, or keypress — clears it and repaints the real layout.
    def flash_all(self, rgb):
        for key in self.keys:
            key.set_led(*rgb)
        self._signal_color = rgb


    # read a line from the serial console
    def read_serial_line(self):
        if usb_cdc.console.in_waiting > 0:
            raw_data = usb_cdc.console.readline()
            try:
                return raw_data.decode("utf-8").strip()
            except UnicodeDecodeError:
                pass
        return None


    # write a prefixed message to the Mac watchdog over serial
    def _serial_write(self, prefix, text):
        try:
            usb_cdc.console.write(f"{prefix}: {text}\n".encode('utf-8'))
        except Exception as e:
            if self.verbose:
                print(f"Serial write error: {e}")


    # send the application name via serial
    def send_application_name(self, app_name):
        self._serial_write("Launch", app_name)


    # send the plugin command via serial
    def send_plugin_command(self, plugin, command):
        # command may include a parameter, e.g. "toggle 'Lamp Name'" — intentional, matches Mac parser
        self._serial_write("Run", f"{plugin}.{command}")


    # forward a message to the Mac watchdog console
    def send_output(self, text):
        self._serial_write("Output", text)


    # set the active config: remember the pristine (unrotated) source and
    # apply the current rotation to it — rotation is absolute, never compounded
    def _set_current_config(self, config):
        self._unrotated_config = config
        self.current_config = self._rotated(config)


    # switch to a top-level layout: any open folder state is discarded —
    # the invariant lives here, not in caller choreography
    def _set_top_config(self, config):
        self.folder_stack = []
        self.autoclose_current_folder = False
        self._set_current_config(config)


    # return a rotated copy of a config (or the config itself if no rotation)
    def _rotated(self, config):
        if self.rotate == "CW":
            return {i: config[cw] for i, cw in enumerate(self.CW) if cw in config}
        elif self.rotate == "CCW":
            return {i: config[ccw] for i, ccw in enumerate(self.CCW) if ccw in config}
        return config



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


    # convert the color string (hex "#RRGGBB" or a named color) to an RGB tuple
    def color_string_to_tuple(self, color_string):
        if not color_string or not isinstance(color_string, str):
            return None
        if color_string.startswith("#"):
            try:
                return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
            except ValueError:
                raise ValueError(f"Invalid hex color: '{color_string}'")
        return NAMED_COLORS.get(color_string.strip().lower())


    # resolve a color config field, rejecting unresolvable non-empty values at
    # load time (an unknown color must not crash update_keys mid-session)
    def _color_from_config(self, config, field):
        value = config.get(field, '')
        color = self.color_string_to_tuple(value)
        if value and color is None:
            raise ValueError(f"Unknown color '{value}' for '{field}'")
        return color


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


    # convert a list-sequence item: strings become keycode tuples, numbers
    # become float delays (a JSON `1` must not end up as keycode 1)
    def convert_value(self, value):
        if isinstance(value, str):
            return self.keycode_string_to_tuple (value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
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

            'color': self._color_from_config(config, 'color'),
            'toggleColor': self._color_from_config(config, 'toggleColor'),
            'pressedColor': self._color_from_config(config, 'pressedColor'),

            'string': config.get('string', ''),
            'string_delay': config.get('string_delay', 0.05),

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
                    try:
                        config_items = self.get_config_items(config)
                    except ValueError as e:
                        self.send_output(f"Config error key {key}: {e}")
                        continue
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
                try:
                    config_items = self.get_config_items(config)
                except ValueError as e:
                    self.send_output(f"Config error key {key}: {e}")
                    continue
                if config_items['folder'] and config_items['folder'] not in json_data.get("folders", {}):
                    folder_name = config_items['folder']
                    print(f"Error: Folder '{folder_name}' not found. Disabling key binding.")
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
            try:
                config_items = self.get_config_items(value)
            except ValueError as e:
                self.send_output(f"Config error key {key}: {e}")
                continue
            # check if the folder exists
            if config_items['folder'] and config_items['folder'] not in json_data.get("folders", {}):
                folder_name = config_items['folder']
                print(f"Error: Folder '{folder_name}' not found. Disabling key binding.")
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
                chained = resolved['alias_of']
                print(f"Error: Chained alias not supported: '{app}' -> '{alias_target}' -> '{chained}'")
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
                try:
                    config_items = self.get_config_items(value)
                except ValueError as e:
                    self.send_output(f"Config error key {key}: {e}")
                    continue
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
            # keep the real reason — this may be a permission error, not a missing file
            raise type(e)(f"Cannot open config file '{json_filename}': {e}") from None
        except ValueError as e:
            raise ValueError(f"Invalid JSON in '{json_filename}': {e}") from None


    # process the rotate serial command
    def process_rotate(self, serial_str):
        value = serial_str[8:].upper()
        if value not in ("CW", "CCW", ""):
            print(f"Warning: Invalid rotation value '{value}', ignoring")
            return
        self.rotate = value
        # re-apply to the pristine config — setting a rotation, not adding one
        self._set_current_config(self._unrotated_config)
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
            config = self.urls[url]
        else:
            config = self.apps.get(app_name, self.apps.get("_otherwise", {}))
        self._set_top_config(config)
        self.update_keys()


    # process the Claude serial command (Mac -> Pico from claude plugin / hooks)
    def process_flash(self, serial_str):
        color = serial_str[8:].strip().lower()
        if color in FLASH_COLORS:
            self.flash_all(FLASH_COLORS[color])


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
        self._set_top_config({})


    # Load the basic/default config (the _otherwise app)
    def load_basic_config(self):
        self._set_top_config(self.apps.get("_otherwise", {}))
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
            self.last_heartbeat = time.monotonic()
            return

        # HELLO: host started -> clear keypad then load basic config
        if serial_str.startswith("HELLO"):
            self.clear_keypad()
            self.load_basic_config()
            self.last_heartbeat = time.monotonic()
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
        elif serial_str.startswith("Claude: "):
            self.process_flash(serial_str)


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
                if (not self.unloaded) and (time.monotonic() - self.last_heartbeat > PICO_TIMEOUT_SECONDS):
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

