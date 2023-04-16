
# DIY Stream Deck with the Pimoroni RGB Keypad

This project uses a Raspberry Pi Pico microcontroller and an [Pimoroni RGB Keypad](https://shop.pimoroni.com/products/pico-rgb-keypad-base) to provide dynamic app-specific shortcut keys. By monitoring the currently active app on your computer, it automatically loads and displays relevant shortcuts to streamline your workflow and increase productivity.

![Keypad with Zoom Shortcuts](images/keypad.png)

If you find this project helpful please consider giving it a ⭐️ at [GitHub](https://github.com/LennartHennigs/ESPTelnet) and/or [buy me a ☕️](https://ko-fi.com/lennart0815). Thanks!


**Note:** This was a (very successful) experiment with ChatGPT-4. I built this without any knowledge of (Micro-)Python. The goal was to not program it myself but tell ChatGPT-4 what I wanted. This is the result. It wrote the code and this README as well. This paragraph here is the only piece I am writing myself (and maybe two lines of code in the CicuitPython code).

## Features

- Dynamically detects the active app and updates the keypad with its shortcuts
- Customizable shortcut keys per app via an easy-to-edit JSON configuration file
- Color-coded keys for better organization and quick identification
- Uses CircuitPython for easy modification and updates

## Hardware Requirements

- Raspberry Pi Pico
- Pimoroni RGB Keypad for Raspberry Pi Pico
- Micro-USB cable to connect the Pi Pico to your computer

## Getting Started

- Install CircuitPython on your Raspberry Pi Pico following the instructions [here](https://learn.adafruit.com/welcome-to-circuitpython/installing-circuitpython).
- Install the required CircuitPython libraries by following the instructions [here](https://learn.adafruit.com/welcome-to-circuitpython/circuitpython-libraries).
- Clone this repository and copy the contents to your Raspberry Pi Pico.
- Edit the `key_def.json` file to configure the shortcut keys and colors for your desired apps.

## Configuration

The `key_def.json` file contains the key configurations for each app. Each app is defined as a JSON object with key-value pairs, where the key is the key number (0-15) and the value is an array with two elements:

The first element is either a string or an array containing the keycodes, representing the shortcut. If a string is provided, it should contain the keycodes separated by '+' (e.g., "CTRL+ALT+T"). If an array is provided, it should contain the keycodes as separate elements (e.g., ["CTRL", "ALT", "T"]).
In addition to specifying key combinations, you can also add delays between key presses within a shortcut. To do this, simply include a floating-point number in the list of keys for a specific shortcut in the `key_def.json` file. This number represents the delay in seconds between key presses.
The second element is a string representing the color of the key. The available colors are "RED", "GREEN", "BLUE", "YELLOW", "ORANGE", "WHITE", and "BLACK".
For example, the configuration for the app "App1" could look like this:

``` json
{
  "App1": {
    "0": ["CTRL+ALT+T", "#FF0000"],
    "1": ["CTRL+C", "#FF0000"],
    "2": ["CTRL+V", "#00FF00"],
    "3": [["TAB", "S"], "#FF0000"],
    "15": [["GUI+W", 0.1, "RETURN"], "#0000FF"]
  }
}
```

## Watchdog

To enable the dynamic detection of the active app, you need to run a watchdog script on your computer that sends the active app's name to the Pi Pico via USB serial. This project includes a Python watchdog script specifically designed for macOS.

To run the watchdog script, navigate to the directory containing the watchdog.py file and execute the following command, e.g.:

``` bash
python3 watchdog.py --port /dev/cu.usbmodem2101 --speed 9600 --verbose
```

- The `--port` parameter should be set to the USB serial port corresponding to your Raspberry Pi Pico (e.g., `/dev/cu.usbmodem2101`).
- The `--speed` parameter should be set to the desired baud rate for the serial communication (e.g., `9600`). 
- If the `--verbose` parameter is set, the current app will be printed to the console.

When the watchdog script detects a change in the active app, it sends the app's name as a single line over the USB serial connection. The Pi Pico then reads this information, loads the corresponding shortcuts from the `key_def.json` file, and updates the keypad accordingly.
