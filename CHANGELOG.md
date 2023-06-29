
# CHANGELOG

## 06-29-2023

- Fixed a bug that Safari and Chrome reported an error when there are no open windows an thus no URLS
- "Empty" tabs are also no longer reported as url

## 06-03-2023

- You can now define keys for Safari and Chrome URLs via the  `urls` section in the JSON
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
- Fixed a bug -  the active app is now "remembered"
- Removed unneeded `action: open_folder` in JSON and code

## 05-06-2023

- Added folder definitions in JSON and code
- Buttons can now launch applications, introduced `application` key to JSON

## 04-23-2023

- Initial version
