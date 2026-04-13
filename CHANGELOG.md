
# CHANGELOG

## 2026-04-13 (second-pass fixes)

- **Watchdog `_get_app_name`: never returns `None`** — if `localizedName()`, `bundleIdentifier()`, and `bundleExecutable()` all return falsy, callers would receive `None` and crash on string concatenation in `_serial_write`. Added `or "unknown"` final fallback.
- **Spotify `play()`: log "No active device"** — the `current_playback is None` early-return was silently swallowing the no-device case. Added `self._log("No active device")` to match the behavior of `pause()` and `play_pause()`.
- **Spotify `_adjust_volume`: explicit `device` key guard** — direct `playback['device']['volume_percent']` access would raise `KeyError` if `playback` is `None` or lacks the `'device'` key. Added explicit guard that logs "No active device" and returns early.
- **Pi Pico `color_string_to_tuple`: wrap invalid hex in `ValueError`** — a malformed color like `"#GGGGGG"` raised a raw Python `ValueError` with a cryptic message. Now caught and re-raised as `ValueError(f"Invalid hex color: {color_string!r}")`.
- **Pi Pico rotation: warn and ignore invalid values** — rotation settings like `"northwest"` were silently accepted and stored, causing `rotate_keys_if_needed()` to fall through as a no-op with no feedback. Now prints a warning and resets to `''`.
- **Watchdog `run_plugin_command`: verbose guard for "Command not found"** — the "Command not found" message always printed regardless of `--verbose`, while all surrounding diagnostics respected it. Added `if self.args.verbose` guard for consistency.
- **Sounds plugin `_futures`: cap list to 10** — completed futures were filtered on each `play()` call but the list was never capped. After many plays in a session, hundreds of done futures would accumulate. Added `[-10:]` slice after filtering.
- **Spotify `play()`: add exception handling around `start_playback()`** — the API call was unguarded while `pause()`, `next()`, `prev()`, and `play_pause()` all wrapped their calls in try/except. Now consistent.
- **Spotify `next()` / `prev()`: remove unused exception variable** — `except Exception as e` had `e` unused; simplified to `except Exception`.

## 2026-04-13 (cleanup)

- **Hue plugin: eliminate double bridge lookup in `toggle`** — `toggle()` called `_find_light()` then passed the raw identifier to `_change_light_state()`, which called `_find_light()` again. Fixed by widening `_change_light_state` to accept an already-resolved light object; `toggle()` now passes the resolved object directly.
- **Sounds plugin: cache `_sound_base_dir`** — `play()` recomputed the base directory path (3 syscalls) on every invocation. Moved the computation to `__init__` as `self._sound_base_dir`.
- **Sounds plugin: prune completed futures** — `self._futures` grew unbounded between `stop()` calls. Added a prune step in `play()` before appending the new future.
- **Spotify plugin: remove dead code** — removed unused `check_active_device` parameter from `play()` and `pause()`, removed unnecessary `else` after `return False` in `has_active_device`, removed `pass;` semicolons.
- **Watchdog: fix `run_loop` local variable shadowing module function** — renamed local `run_loop` variable in `run_loop()` to `ns_run_loop`.
- **Watchdog: extract `_serial_write` helper** — `send_hello` and `send_bye` had identical try/except structure; extracted to `_serial_write(message, label)`.
- **Watchdog: capture `plugin.commands()` once** — `run_plugin_command` called `plugin.commands()` twice per invocation; now captured once.
- **Watchdog: remove commented-out blocks and unreachable code** — removed dead comment block in `applicationTerminated_`, removed unreachable `return` after `pass` in `launch_app`, fixed trailing space in `if args.rotate :`.
- **Pi Pico: remove trailing semicolons** — removed Python anti-pattern semicolons from `code.py` (lines 138–141, 170, 335, 382).
- **Pi Pico: rename camelCase `someAction` → `some_action`** — renamed in `key_press_action`, `key_release_action`, and `close_folder_if_needed`.
- **Pi Pico: promote derived constant to module level** — `TIMEOUT_SECONDS` was recomputed inside `run()` on every call; replaced with module-level `PICO_TIMEOUT_SECONDS = PICO_HEARTBEAT_INTERVAL * PICO_TIMEOUT_MULTIPLIER`.

## 2026-04-13

- **Hue plugin: `_find_light()` int logic fixed** — integer lamp identifiers previously matched every light in the list because the bounds check `lamp_identifier < len(lights)` is true for all indices. Replaced three methods (`_find_light`, `_get_lights`, `_is_matching_light`) with a single correct implementation that looks up the light at the specified list index.
- **Sounds plugin: executor permanently killed by `stop()`** — `stop()` called `executor.shutdown()`, making the executor unusable for subsequent `play()` calls. Fixed by shutting down the old executor and replacing it with a fresh one so subsequent `play()` calls succeed.
- **Sounds plugin: security exceptions double-wrapped** — path traversal and other validation errors raised inside the outer `try` block were caught and re-raised as `"Failed to play … : Invalid filename …"`. Moved security validation above the `try` block so errors surface cleanly.
- **Pi Pico `parse_json()`: no error handling** — missing or malformed config files crashed the controller with a bare exception. Added `try/except` that preserves the original exception type and adds the filename to the message.
- **Pi Pico: `KeyError` when config has no `folders` key** — three `json_data["folders"]` accesses raised `KeyError` for configs that omit the `folders` section. Changed to `json_data.get("folders", {})`.
- **Watchdog: `VERSION` not interpolated in startup print** — missing f-string prefix meant the version literal `{VERSION}` was printed instead of the value.
- **Watchdog: dead variable `running = [True]`** — unused variable removed.
- **Watchdog: wrong return type annotation** — `send_app_name_to_microcontroller` annotated `-> str`; corrected to `-> None`.
- **Spotify: trailing comma in OAuth scope** — `scope` string ended with a comma, producing an empty scope element. Removed commas (Spotify scope is space-delimited).
- **Spotify credentials purged from git history** — client ID and secret were committed in `src/mac/plugins_config/spotify.json`. Rewrote all history blobs with `git filter-repo`; file now contains placeholder values.
- **Plugin config files excluded from git** — added `src/mac/plugins_config/*.json` to `.gitignore`. Example templates (`*.json.example`) remain tracked.
- Added `src/mac/plugins_config/spotify.json.example`, `hue.json.example`, and `sounds.json.example` as credential/config templates.
- Added `tests/unit/mac/plugins/test_hue_plugin.py` (16 tests): turn on/off/toggle by name and index, unknown lights, verbose output, config errors.
- Extended `tests/unit/mac/plugins/test_sounds_plugin.py` with 6 tests: stop-then-play, multiple stops, security message format, missing file, empty filename.
- Extended `tests/unit/pico/test_config_loader.py` with 4 tests: `parse_json` error handling, `process_global_section`/`process_config` with no `folders` key.
- Added `tests/unit/mac/test_watchdog.py` (14 tests): source-inspection (VERSION f-string, dead variable, return type), functional heartbeat send/stop/exception-handling, HELLO/BYE message format, and heartbeat thread lifecycle.

## 2025-09-08

### Bug Fixes

- **Fixed Hue plugin initialization error** — removed obsolete `_ping` method call from `HuePlugin` that was causing initialization failure after heartbeat system updates.

## 2025-09-02

- **Comprehensive Pi Pico test suite** — 85+ new tests covering all Pi Pico functionality:
  - Configuration loading (14 tests) — JSON parsing, validation, keycodes
  - Core controller (14 tests) — initialization, serial commands, basic functionality
  - Keypad functionality (20 tests) — key press/release, LEDs, folders, plugins
  - Heartbeat system (18 tests) — timeout detection, recovery, edge cases
  - JSON corruption (19 tests) — malformed JSON handling and error recovery
- **Mock CircuitPython framework** — complete hardware simulation for testing without physical device.
- **Test runner script** (`run-tests.sh`) — convenient script for running test categories.
- **Security vulnerability tests** — path traversal and injection attack tests.
- **Improved heartbeat** — watchdog sends "HB" instead of "." for protocol clarity.
- **HELLO/BYE handshake** — startup/shutdown messages with version information.
- **Echo diagnostics** — lightweight echo command for connection testing.
- **Heartbeat timeout detection** — Pi Pico unloads keypad on host disconnection.

## 2025-09-01

- Replaced unsafe shell-based ping with a validated subprocess-based `_ping` (in `src/mac/plugins/base_plugin.py`) to prevent command injection and validate IPs.
- Made `src` a proper package; migrated plugin imports to package-absolute imports.
- Added `__init__.py` in `src/`, `src/mac/`, and `src/mac/plugins/`.
- Added `run-mac-watchdog.sh` launcher with `PYTHONPATH` setup.
- Updated `.gitignore` with common ignores (`test_venv/`, `.coverage`, `.claude`).
- Added per-component requirement files (`src/mac/requirements.txt`, `src/pi_pico/requirements.txt`).

## 2024-01-31

- Refactored plugin loading and error handling.

## 2024-01-27

- `spotify.py`: added credential validation on startup.
- `hue.py`: verifies bridge IP and connection on startup.
- `watchdog.py`: new Cocoa selector signature encoding.

## 2024-01-19

- `code.py` / `watchdog.py`: detect app termination and reset `toggleColor` state.

## 2024-01-15

- `code.py`: added `pressedColor` and `toggleColor` parameters.

## 2024-01-12

- `watchdog.py`: handle empty localized app names.
- `code.py`: added `pressedUntilReleased` parameter.

## 2024-01-03

- `code.py`: added `alias_of` parameter for applications.
- `code.py`: moved `global` section inside `applications` as `_default`.
- `code.py`: renamed `ignore_globals` → `ignore_default`.

## 2023-12-12

- Added `settings` section to JSON config with `rotate` parameter.
- Added `--rotate` parameter (`CW`/`CCW`) to `watchdog.py`.
- Added heartbeat to `watchdog.py`.
- Refactored `watchdog.py` and added error handling to `load_plugins()`.
- Added `App:` prefix to serial commands from watchdog.
- Fixed: button color now properly resets after a key sequence.

## 2023-11-02 – 2023-11-05

- Added `CMD` as alias for `GUI` in key definitions.
- Added `autoclose` key for folders (default `true`).
- Keys now trigger on release only.
- Refactored JSON loading and parsing functions.

## 2023-06-29

- Fixed Safari/Chrome error when no windows are open.

## 2023-06-03

- Added `urls` section for Safari/Chrome URL-specific keys.
- Added `global` section for default key definitions.
- Added `"ignore_globals": "true"` flag.
- Added nested folder support.

## 2023-05-22

- Added audio playback plugin.

## 2023-05-20

- Added Philips Hue plugin.

## 2023-05-18

- Added Spotify plugin and plugin system.

## 2023-05-12

- Safari and Chrome return the URL of the active tab.

## 2023-05-11

- Stopping the code turns off the keypad.
- Fixed: active app is now remembered correctly.
- Removed unneeded `action: open_folder`.

## 2023-05-06

- Added folder definitions.
- Added `application` key type for launching apps.

## 2023-04-23

- Initial version.
