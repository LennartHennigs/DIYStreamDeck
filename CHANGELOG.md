
# CHANGELOG

## 2025-09-01

### Security

- Replaced unsafe shell-based ping with a validated subprocess-based `_ping` (in
  `src/mac/plugins/base_plugin.py`) to prevent command injection and validate IPs.

### Fixes

- `SoundsPlugin` now tracks ThreadPool futures and implements a robust `stop()`
  that cancels outstanding futures and shuts down the executor
  (`src/mac/plugins/sounds.py`).

### Tests

- Added unit tests and security tests. New tests include:
  - `tests/unit/mac/plugins/test_base_plugin_ping.py`
  - `tests/unit/mac/plugins/test_sounds_plugin.py`
  - additional unit and security tests under `tests/` (pytest config and test
    requirements added).
  - Added `tests/unit/mac/plugins/test_load_plugins_config.py` to assert that
    the plugin loader prefers the centralized `src/mac/plugins_config/<name>.json`,
    falls back to `src/mac/plugins/config/<name>.json` when necessary, and skips
    plugins with no configuration file.

### Packaging & imports

- Made `src` a proper package and migrated plugin imports to package-absolute
  imports (e.g. `from src.mac.plugins.base_plugin import BasePlugin`). Added
  `__init__.py` in `src/`, `src/mac/`, and `src/mac/plugins/`.

### Tooling

- Added `run-mac-watchdog.sh` launcher that respects a local `.venv` and sets
  `PYTHONPATH`, and added `README-run-mac-watchdog.md` with bootstrap/run
  instructions.

### Repo hygiene & misc

- Updated `.gitignore` with common ignores (`test_venv/`, `.coverage`, `.claude`).
- Added CLAUDE-related metadata files and restructured `src/` layout with
  per-component requirement files (`src/mac/requirements.txt`,
  `src/pi_pico/requirements.txt`).

## 2024-01-31

- some refactoring

## 2024-01-27

- Made plugins more robust
  - `spotify.py` now checks if credentials work
  - `hue.py` checks if IP of bridge exists and verifies connection
- `watchdog.py` has new Cocoa signature encoding

## 2024-01-19

- `code.py` and `watchdog.py`: added detection of app termination to reset `toggleColor` settings

## 2024-01-15

- `code.py`: added `pressedColor` and `toggleColor` parameters for key definitions.

## 2024-01-12

- `watchdog.py`: detects if localized app name is empty and uses different strings to identify the app
- `code.py`: added `pressedUntilReleased` parameter to key definition

## 2024-01-03

- `code.py`: added `alias_of` parameter for applications to reuse key definitions
- `code.py`: moved the `global` section inside the `applications` section and renamed it to `_default`
- `code.py`: renamed `ignore_globals` to `ignore_default`

## 2023-12-12

- added `settings` section to JSON file. You can now define the `rotate` parameter there.
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
