
# CHANGELOG

## 2026-04-16 (code review fixes)

- **Pi Pico `get_config_items`: fix `pressedUntilReleased` default** — defaulted to empty string `''` instead of `False`, causing semantic type mismatch. Changed to `False`.
- **Pi Pico `key_press_action`: fix `pressedColor` for all action types** — `pressedColor` LED was only applied inside the `elif keys:` branch; plugin commands and app launches never showed the pressed color. Moved after the full if/elif chain, guarded against folders.
- **Pi Pico `keycode_string_to_tuple`: reject empty keycode strings** — empty or whitespace-only strings split to `['']` and gave an unhelpful "Unknown keycode" error. Added early guard raising `ValueError("Empty key_sequence string")`.
- **Pi Pico: validate key numbers are in 0-15 range** — out-of-range keys like `"999"` or `"-1"` were silently accepted, creating dead config entries wasting heap. Added `_validate_key_number()` helper; out-of-range keys are now dropped with a warning.
- **Pi Pico `parse_json`: include filename in ValueError** — CircuitPython raises `ValueError` for malformed JSON (not `JSONDecodeError`). The error now wraps the original message with the filename for easier debugging. Updated corruption tests to expect `ValueError` instead of `json.JSONDecodeError`.
- **Pi Pico `__init__`: guard KEYCODE_MAPPING against redundant rebuild** — `KEYCODE_MAPPING` dict comprehension ran on every `KeyController()` instantiation. Added `if ... is None` guard so it's built once and shared across instances.
- **Pi Pico `run()`: log heartbeat check errors when verbose** — broad `except Exception: pass` in the heartbeat timeout check now logs the error when `verbose=True`.
- **Watchdog `_serial_write`: use UTF-8 encoding** — was encoding with `'ascii', 'replace'`, silently corrupting non-ASCII app names (e.g. accented characters became `?`). Changed to UTF-8, matching the Pico's `decode("utf-8")`.
- **Watchdog: rename `send_heartbeat` to `_run_heartbeat_loop`** — name suggested a one-time send; it's actually a blocking loop for a thread.
- **Spotify plugin: guard against logging None song info** — `get_current_song_info()` returns `None` when no track is playing; `_log(None)` printed literal "None". Added guard to only log when song info is available.
- **`run-tests.sh`: add `set -e` for fail-fast** — script continued after failures (e.g. venv activation fails).
- **Docs: fix stale test counts, wrong file references** — updated "208 tests" → 218 in `README.md`, `CLAUDE.md`, `run-tests.sh`. Fixed `requirements/requirements_mac.txt` → `src/mac/requirements.txt` in `CLAUDE.md`. Fixed wrong test filenames in `tests/CLAUDE.md` (`test_core_controller.py` → `test_key_controller.py`, `test_heartbeat.py` → `test_heartbeat_functionality.py`). Added missing `test_actual_vulnerabilities.py` to directory tree. Updated "150+" → 218 test count.
- **CLAUDE.md: remove README duplication, fix protocol table** — removed Key Configuration and Plugin System sections that duplicated README content. Fixed Communication Protocol table: added 5 missing messages (`Rotate:`, `Terminated:`, `Launch:`, `Run:`, `ECHO`), corrected `ECHO` direction (Pico→Mac, not Mac→Pico), added `HELLO:<version>` format. Removed Notes section (items already covered elsewhere). Added `code.py`, `tests/`, `CHANGELOG.md` to File Locations. Added cross-reference to README for user-facing docs.

## 2026-04-16 (quality fixes + refactors)

- **Watchdog: remove unused imports** — `contextmanager` and `List` (from `typing`) were imported but never used; removed both. `Tuple` was also removed after `load_plugin_module` was inlined.
- **Watchdog: move `run_loop()` onto `WatchDog`** — standalone `run_loop(observer)` function refactored into `WatchDog.run_loop(self)` for cleaner encapsulation.
- **Watchdog: inline `load_plugin_module` into `load_plugins`** — `load_plugin_module` was a thin helper called once, returning a `(None, None)` sentinel on error. Inlined with clear stage comments (load module → find config → instantiate), eliminating the sentinel pattern.
- **Watchdog `get_url`: log `osascript` stderr when verbose** — `error` from `osa.communicate()` was captured but never used. Added `stderr=subprocess.PIPE` and a verbose-gated print for the error output.
- **`base_plugin._log_and_raise`: always print errors** — error messages (config not found, invalid filename, etc.) were gated behind `verbose`. Replaced `self._log(msg)` with `print(msg)` so failures are always visible.
- **Pi Pico `get_config_items`: remove alias dead code** — two unreachable `alias_of` checks inside `get_config_items` (lines 277–286) were removed. Aliases are fully resolved by `load_single_app_config` before this method is called; the checks were dead and the first one replaced the dict with a string, which would have crashed on the subsequent `.get()` calls.
- **Pi Pico `run()`: call `keypad.update()` unconditionally** — `keypad.update()` was only called in the `else` (idle-serial) branch. During a burst of serial messages, physical key presses were silently dropped. Moved `keypad.update()` outside the `else` branch so it runs every loop iteration.
- **Pi Pico `process_url_section`: apply global config to URL contexts** — `add_global_config()` was called for app and folder sections but not for URL sections, causing `_default` keys (e.g. folder shortcuts) to disappear when a browser URL was active. Added `self.add_global_config(urls[url])` at the end of each URL entry.
- **Pi Pico `send_plugin_command`: document parameter behaviour** — added a comment clarifying that `command` may include a parameter (e.g., `"toggle 'Lamp Name'"`), matching the Mac parser's expected format.
- Updated test count to 208 in `README.md`, `CLAUDE.md`, and `run-tests.sh`.

## 2026-04-14 (third-pass fixes)

- **Watchdog `main()` Rotate command: route through `_serial_write`** — `Rotate:` was written directly to `ser` bypassing `_serial_lock`, creating a race with the heartbeat thread. Replaced bare `ser.write(...)` with `watchdog._serial_write(...)`.
- **Watchdog `main()`: close serial port in `finally`** — `ser` was never closed on exit; the port remained locked until the OS reclaimed it. Added `ser.close()` after `heartbeat_thread.join()`.
- **Watchdog `launch_app`: security rejection always prints** — "Refused unsafe app name" was gated behind `if self.args.verbose`, silently swallowing potential attack attempts in non-verbose mode. Removed the verbose guard so rejections always print.
- **Watchdog `run_plugin_command`: verbose-gate parameter error messages** — "Parameter missing" and "Invalid parameter" always printed regardless of `--verbose`, inconsistent with surrounding diagnostics. Added `if self.args.verbose:` guards.
- **Pi Pico `parse_json` comment: fix `JSONDecodeError` reference** — comment said `json.JSONDecodeError` propagates; CircuitPython raises plain `ValueError` (`JSONDecodeError` doesn't exist there). Updated comment to say `ValueError`.
- **Pi Pico `process_config`: remove dead `key_sequences = ()` line** — the line set `config_items['key_sequences'] = ()` inside the invalid-folder branch, but `config_items` was never added to `app_config` in that branch anyway. Dead line with no effect; removed.
- **`CLAUDE.md`: document CircuitPython constraints** — added explicit note that `code.py` runs on CircuitPython (no `threading`, no `.with_traceback()`, no `json.JSONDecodeError`, no `errno`, ~200 KB heap).
- **Tests: `TestSelfReferenceAlias`** — 2 tests documenting that `load_single_app_config` with `alias_of == app` already returns `None` via the existing chaining guard.
- **Tests: `TestRotateSerialWrite`** — 1 source-inspection test verifying the Rotate block uses `_serial_write`, not bare `ser.write`.
- Updated test count to 204 in `README.md`, `CLAUDE.md`, and `run-tests.sh`.

## 2026-04-13 (code review + simplify)

- **Pi Pico `parse_json`: fix CircuitPython incompatibility** — `.with_traceback(e.__traceback__)` is not supported in CircuitPython; removed it. Exception type is still preserved via `raise type(e)(...)`.
- **Pi Pico `process_rotate`: validate serial input** — runtime `Rotate:` commands from the watchdog were stored without validation, unlike the `__init__` path. Added the same `("CW", "CCW", "")` guard with a warning print so invalid values are ignored.
- **`BasePlugin`: add `__init__`** — subclasses had to set `self.verbose` before calling `self._load_config()`; if a future plugin got the order wrong, `_log()` would crash with `AttributeError`. `BasePlugin.__init__` now guarantees the correct order.
- **`SpotifyPlugin`, `SoundsPlugin`, `HuePlugin`: use `super().__init__()`** — all three plugins previously duplicated `self.verbose = verbose; self.config = self._load_config(config_file)`. Now delegate to the base class.
- **`SpotifyPlugin`: log exception details** — six bare `except Exception` blocks logged only `"Error"`. Changed to `except Exception as e: self._log(f"Error: {e}")` so failures are diagnosable.
- **Watchdog: remove unused imports** — `termios`, `tty`, and `time` were imported but never referenced; removed.
- **Watchdog `send_heartbeat`: use `threading.Event` for clean shutdown** — replaced `while self.running: time.sleep(HEARTBEAT_INTERVAL)` with `while not self._stop_event.wait(HEARTBEAT_INTERVAL)`. The thread now wakes immediately on shutdown instead of waiting up to 2 seconds for a sleep to expire.
- **Watchdog: remove dead `running` class attribute** — `WatchDog.running = True` was the old stop mechanism, superseded by `_stop_event`.
- **Tests: delete orphaned `tests/unit/pi_pico/` directory** — 3 tests superseded by the 17-test `tests/unit/pico/test_heartbeat_functionality.py`; no `__init__.py` existed so they weren't being collected.
- **Tests: update watchdog heartbeat tests** — updated 7 tests to use `patch.object(wdog._stop_event, 'wait', ...)` instead of the removed `running`/`time.sleep` interface.
- Updated test count to 201 in `README.md` and `run-tests.sh`.

## 2026-04-13 (simplify pass)

- **Watchdog `check_serial` ECHO reply: use `_serial_write`** — ECHO response wrote directly to `self.ser` bypassing the serial lock, creating a race with the heartbeat thread. Replaced with `self._serial_write()`.
- **`BasePlugin._log_and_raise`: respect `verbose` flag** — previous implementation called `logging.error()` unconditionally, inconsistent with `_log()` which gates on `verbose`. Replaced with `self._log(msg)` so all plugin error messages respect the verbose setting uniformly.
- **`SoundsPlugin._log_and_raise`: remove override** — `sounds.py` had a local `_log_and_raise` that duplicated the above fix manually. Removed now that `BasePlugin` has the correct implementation.
- **`WatchDog`: pre-compile regex patterns** — `launch_pattern` and `run_pattern` were plain strings recompiled by `re.match()` on every incoming serial command. Changed to `re.compile()` at class level.
- **`WatchDog.launch_app`: reject leading-dash names** — validation blocked `/`, `\`, `\x00` but not names starting with `-`, which could inject flags to `open -a`. Added `or launch_app_name.startswith('-')` guard.

## 2026-04-13 (robustness fixes)

- **Pi Pico `send_application_name` / `send_plugin_command`: log serial write errors** — both methods swallowed all exceptions silently. Serial write failures now print an error message when `verbose=True`, making hardware disconnects and buffer overflows visible during debugging.
- **Mac watchdog `launch_app`: log `CalledProcessError`** — a failed `open -a` call (e.g. app not installed) was caught with `except … pass`. Now prints a failure message when `verbose=True`.
- **Pi Pico `unload_keypad`: idempotent guard** — calling `unload_keypad()` twice would call `clear_keypad()` twice, risking inconsistent hardware state. Added `if self.unloaded: return` early exit.
- **Pi Pico `load_single_app_config`: hard limit on alias depth** — chained aliases (A→B where B also has `alias_of`) previously crashed with `AttributeError`. Now detected and rejected with a clear error message; the offending app is skipped and the rest of the config loads normally.
- **Mac watchdog `get_url`: escape double-quotes in app name before AppleScript interpolation** — defense in depth alongside the existing allowlist. Introduced `safe_app_name = app_name.replace('"', '\\"')` so any future extension of the allowlist cannot introduce injection.
- **Plugins: move `_log` to `BasePlugin`** — `SpotifyPlugin` had its own `_log(message)` helper; `HuePlugin` used bare `print()` that always fired regardless of `verbose`. Consolidated `_log` in `BasePlugin` and updated `HuePlugin` to use it, so missing-light messages respect the `verbose` flag consistently across all plugins.

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
