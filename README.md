
# DIY Streamdeck with the Pimoroni RGB Keypad

This project uses a Raspberry Pi Pico micro controller and an [Pimoroni RGB Keypad](https://shop.pimoroni.com/products/pico-rgb-keypad-base) to provide dynamic app-specific shortcut keys. By monitoring the currently active app on your computer, it automatically loads and displays relevant shortcuts to streamline your workflow and increase productivity.

![Keypad with Zoom Shortcuts](images/keypad.png)

If you find this project helpful please consider giving it a ⭐️ at [GitHub](https://github.com/LennartHennigs/ESPTelnet) and/or [buy me a ☕️](https://ko-fi.com/lennart0815). Thanks!

For the latest changes and the history of changes, please take a look at the [CHANGELOG](https://github.com/LennartHennigs/DIYStreamDeck/blob/main/CHANGELOG.md).

**Note:** This was (and is) a very successful experiment with ChatGPT-4. 🤖 I built this without any knowledge of Python or CircuitPython. The goal was to not program it myself but tell ChatGPT-4 what I wanted. This is the result. It wrote the code and this README as well. This paragraph here is the only piece I am writing myself (and maybe five lines in the CicuitPython code).

## Features

- Allows to assign keyboard shortcuts/key sequences to its keys
- Dynamically detects the active app and updates the keypad with its shortcuts
- Default keypad lapyout can be defined when no app specific layout is defined
- Alternatively, apps can be launched via the keypad 🆕
- You can also define "folders" - a new keypad definition scheme that can be tied to a single key 🆕    
- Keypad definitions are stored and loaded in a JSON configuration file

## Hardware Requirements

- Raspberry Pi Pico
- Pimoroni RGB Keypad for Raspberry Pi Pico
- Micro-USB cable to connect the Pi Pico to your computer

## How it Works

The [`code.py`](https://github.com/LennartHennigs/DIYStreamDeck/blob/main/src/pi_pico/code.py) script reads key definitions from a JSON file and maps them to specific key sequences and LED colors. It listens for the currently active application on the host computer and updates the keypad based on the key mappings for the active application.

The [`watchdog.py`](https://github.com/LennartHennigs/DIYStreamDeck/blob/main/src/mac/watchdog.py) script monitors the currently active application on the host computer and sends its name to the microcontroller connected to the RGB keypad.

## Getting Started

- Install CircuitPython on your Raspberry Pi Pico following the instructions [here](https://learn.adafruit.com/welcome-to-circuitpython/installing-circuitpython).
- Install the required CircuitPython libraries by following the instructions [here](https://learn.adafruit.com/welcome-to-circuitpython/circuitpython-libraries).
- Clone this repository and copy the contents to your Raspberry Pi Pico.
- Edit the [`key_def.json`](https://github.com/LennartHennigs/DIYStreamDeck/blob/main/src/pi_pico/key_def.json) file to configure the shortcut keys and colors for your desired apps.

## Configuration

In the [`key_def.json`](https://github.com/LennartHennigs/DIYStreamDeck/blob/main/src/pi_pico/key_def.json) configuration file, each app is defined as a JSON object with key-value pairs, with two entries: `key_definitions` and `folders`. In the `key_definitions` area the different keys for various apps are defined with the key numbers (0-15). In `folders` key sets can be definied that can be assigned to a key.

These are the possible fields for a key entry:

- `key_sequence`: This field specifies the key combination to be executed when the key is pressed. You can use either a string or an array [to specify the key sequence](https://docs.circuitpython.org/projects/hid/en/latest/_modules/adafruit_hid/keycode.html). If a string is provided, it should contain the keycodes separated by '+' (e.g., "CTRL+ALT+T"). If an array is provided, it should contain the keycodes as separate elements (e.g., ["CTRL", "ALT", "T"]). You can also add delays between key presses within a shortcut by including a floating-point number in the list of keys for a specific shortcut in the key_def.json file. This number represents the delay in seconds between key presses. You can find a list of possible keycodes here.
- `application`: This field is used to specify the application to be launched when an application key is pressed.
- `color`: This field specifies the color of the key, in RGB format. You can specify the color of the key using an RGB string (e.g., "#FF0000" for red, "#00FF00" for green, "#0000FF" for blue).
- `description`: This field provides a description of the function of the key, which is useful for understanding the purpose of each key when printed in the console.
- `folder`: This field allows you assign a "folder" to be opened. The entry also needs the `action` field
- `action`: This field can have the values `open_folder` or `close_folder`. The later is needed inside a folder definition.


With these fields you can define two types of keys, shortcut keys and application launch keys.

- *Shortcut keys* have a `key_sequence` field which specifies the key combination to be executed when the key is pressed.
- *Application keys* have an `application` field which launches the specified application when the key is pressed.
- *Folder keys*  have an `folder` key and an `action: open_folder` field, when the key is pressed it will load the key definitions.

In addition to the regular shortcut keys for an app, there is a special app key called `_otherwise`, which is used as a fallback when no app definition is found in the JSON file. The `_otherwise` key can include its own set of general-purpose shortcut keys, similar to those defined for "App1". When the Python script is running, it constantly monitors the active application on the computer, and if the active application matches any of the keys in the JSON file, the relevant shortcut keys are loaded onto the keypad. If not, the shortcut keys defined under the "_otherwise" key are loaded onto the keypad.

For example, the configuration could look like this:

``` json
{
  "key_definitions": {
    "zoom.us": {
      "0": {
        "key_sequence": [
          "GUI+SHIFT+A"
        ],
        "color": "#FFFF00",
        "description": "Mute/Unmute Audio"
      },
      "1": {
        "key_sequence": [
          "GUI+SHIFT+V"
        ],
        "color": "#FFFF00",
        "description": "Start/Stop Video"
      },
      "15": {
        "key_sequence": [
          "GUI+W",
          0.1,
          "RETURN"
        ],
        "color": "#FF0000",
        "description": "End Meeting"
      }
    },
    "Microsoft Outlook": {
      "0": {
        "key_sequence": [
          "GUI+ONE"
        ],
        "color": "#FFFF00",
        "description": "Switch to Mail"
      },
      "1": {
        "key_sequence": [
          "GUI+TWO"
        ],
        "color": "#FFFF00",
        "description": "Switch to Calendar"
      },
      "3": {
        "key_sequence": [
          "GUI+ALT+N"
        ],
        "color": "#00FF00",
        "description": "New Email"
      }
    },
    "_otherwise": {
      "0": {
        "key_sequence": [
          "GUI+SPACE"
        ],
        "color": "#FFFFFF",
        "description": "Open Spotlight Search"
      },
      "3": {
        "key_sequence": [
          "GUI+LEFT_CONTROL+Q"
        ],
        "color": "#FF0000",
        "description": "Close Application"
      },
      "13": {
        "action": "open_folder",
        "folder": "apps",
        "color": "#FFFFFF",
        "description": "Apps Folder"
      }
    }
  },
  "folders": {
    "apps": {
      "0": {
        "action": "close_folder",
        "color": "#FFFFFF",
        "description": "Close"
      },
      "12": {
        "application": "zoom.us",
        "color": "#0000FF",
        "description": "Launch Zoom"
      },
      "13": {
        "application": "Slack",
        "color": "#FF0000",
        "description": "Launch Slack"
      }
    }
  }
}
```

In the [`key_def.json`](https://github.com/LennartHennigs/DIYStreamDeck/blob/main/src/pi_pico/key_def.json) file, you will find a special app key called `_otherwise`. This key is used to define shortcut keys that are not specific to any particular app. When the Python script is running, it constantly monitors the active application on your computer, and if the active application matches any of the keys in the JSON file, it will load the relevant shortcut keys onto the keypad. If the active application does not match any of the defined keys, the "_otherwise" key is used as a fallback, and the shortcut keys defined under this key are loaded onto the keypad. This means that you can define a set of general-purpose shortcut keys that are always available, regardless of which application is currently active.

## Watchdog

To enable the dynamic detection of the active app, you need to run a watchdog script on your computer that sends the active app's name to the Pi Pico via USB serial. This project includes a Python watchdog script specifically designed for macOS.

To run the watchdog script, navigate to the directory containing the watchdog.py file and execute the following command, e.g.:

``` bash
python3 watchdog.py --port /dev/cu.usbmodem2101 --speed 9600 --verbose
```

- The `--port` parameter needs to be set to the USB serial port corresponding to your Raspberry Pi Pico (e.g., `/dev/cu.usbmodem2101`).
- The optional `--speed` parameter should be set to the desired baud rate for the serial communication (default: `9600`).
- If the optional `--verbose` parameter is set, the current app will be printed to the console.

When the watchdog script detects a change in the active app, it sends the app's name as a single line over the USB serial connection. The Pi Pico then reads this information, loads the corresponding shortcuts from the `key_def.json` file, and updates the keypad accordingly.
