
# CHANGELOG

# 01-27-2024

- made plugins more robust
  - spotify now checks if credentials work
  - hue checks if ip of bridge exists and checks whether connecting to it was successful
  
# 01-19-2024

- added detection of app termination to reset `toggleColor` settings

# 01-15-2024

- added `pressedColor` and `toggleColor` parameters for key definitions.

# 01-12-2024

- `watchdog.py` detects if localized app name is empty a uses different string to identify app
- added `pressedUntilReleased` parameter to key definition

# 01-03-2024

- added `alias_of` parameter for applications, to reuse key definitions
- moved the `global` section inside the `applications` section and renamed it to `_default`
- renamed `ignore_globals` to `ignore_default`

## 12-12-2023

- added `settings` section to JSON file. You can now define the `rotate`` parameter there, too.
- added `--rotate` parameter (`CW` or `CCW`) to `watchdog.py`
- added heartbeat to `watchdog.py` (code for it still missing on client)
- refactored the code of `watchdog.py`
- added error handling to `load_plugins()`
- added version number display to `watchdog.py`
- fixed verbose output for commands and apps
- added `App:` prefix to serial command from `watchdog.py` to the keypad
- fixed: button color is now properly reset after a key sequence

## 11-02-2023 - 11-05-2023

- It is now possible to use `CMD` instead of `GUI` in the JSON key definition (to make my life easier).
- Added `autoclose` key for folders (default = `true``). Allows to specify whether a folder should be kept open after an action.
- Keys are now only triggered on release – no more multiple shortcuts are being triggered
- Refactored functions that deal with loading and parsing of the JSON
- Simplified the `key_action` and `handle_key_sequences` functions

## 06-29-2023

- Fixed a bug that Safari and Chrome reported an error when there are no open windows an thus no URLS
- "Empty" tabs are also no longer reported as url

## 06-03-2023

- You can now define keys for Safari and Chrome URLs via the `urls` section in the JSON
- There is now a `global` section for default key definitions
- You can define `"ignore_globals": "true"` for folders and apps where `global` keys should not be used
- You can now nest folders

## 05-22-2023

- Added a Audio playback plugin

## 05-20-2023

- Added a Hue plugin

## 05-18-2023

- Added a Spotify plugin
- Added Plugin capabilities to the Streamdeck

## 05-12-2023

- Safari and Chrome now also return the URL of the active tab

## 05-11-2023

- Stopping the code will turn off the keypad
- Fixed a bug - the active app is now "remembered"
- Removed unneeded `action: open_folder` in JSON and code

## 05-06-2023

- Added folder definitions in JSON and code
- Buttons can now launch applications, introduced `application` key to JSON

## 04-23-2023

- Initial version
