# CLAUDE.md

Guidance for Claude Code when working in this repository. See [README.md](README.md) for user-facing setup, configuration, and plugin documentation.

## Project Overview

DIY StreamDeck using a Raspberry Pi Pico + Pimoroni RGB Keypad. Two components:

- **Pi Pico** (`src/pi_pico/`): CircuitPython (`code.py`, `KeyController` class) — reads `key_def.json`, drives LEDs, sends HID events.
  **`code.py` is CircuitPython, not CPython.** Constraints: no `threading`, no `.with_traceback()`, no `json.JSONDecodeError` (raises plain `ValueError`), no `errno` module, ~200 KB heap. Use `time.monotonic()` for timing — `time.time()` is integer-second resolution on the Pico (no RTC). Keep changes minimal — every extra import and line costs RAM.
- **Mac Watchdog** (`src/mac/`): Python (`watchdog.py`, `WatchDog` class) — detects active app via Cocoa/NSWorkspace, sends app name to Pico over USB serial, executes plugin commands.

`_default` keys merge into every app, folder, and URL layout unless `ignore_default: true`. `_otherwise` is the fallback layout for apps without a specific definition.

macOS fires `NSWorkspaceDidActivateApplicationNotification` on many events that don't actually change the active app (focus flicker, background helpers). `send_app_name_to_microcontroller` dedups on `_last_sent_app_name` to avoid spurious `App:` writes that would repaint LEDs (and wipe any active Claude signal color) on the Pico.

### Communication Protocol

| Message | Direction | Purpose |
| --- | --- | --- |
| `HELLO:<version>` | Mac → Pico | Startup handshake |
| `BYE` | Mac → Pico | Shutdown handshake |
| `HB` | Mac → Pico | Heartbeat keepalive |
| `App: <name>` | Mac → Pico | Active application changed |
| `Rotate: CW\|CCW` | Mac → Pico | Rotate keypad layout |
| `Terminated: <name>` | Mac → Pico | App terminated (resets toggle state) |
| `Claude: green\|red\|yellow` | Mac → Pico | Flood-fill LEDs; color persists until app switch, rotation, keypress (ack-only — the dismissing press does not trigger the key), next signal, `Claude: clear`, or the plugin's `timeout_seconds` (claude plugin / Claude Code hooks) |
| `Claude: clear` | Mac → Pico | Repaint the real layout, clearing any active signal (sent by the `UserPromptSubmit` hook on reply, or by the claude plugin's auto-clear timer) |
| `Launch: <name>` | Pico → Mac | Request app launch |
| `Run: <plugin.cmd>` | Pico → Mac | Request plugin command |
| `Output: <text>` | Pico → Mac | Forward text to Mac console (`[Pico] <text>`) |
| `ECHO[:<token>]` | Pico → Mac | Connection test (watchdog replies `ECHO-OK`) |

Pico unloads the keypad if heartbeats stop (host disconnected).

## File Locations

| Path | Purpose |
| --- | --- |
| `src/pi_pico/code.py` | Pico firmware (CircuitPython) |
| `src/pi_pico/key_def.json` | Key layout configuration (repo copy = first-run seed source) |
| `~/Documents/DIYStreamDeck/` | **Runtime** config folder: `key_def.json` + flat plugin `<name>.json`. Seeded on first run; used by the `.app` and source runs. Override with `STREAMDECK_CONFIG_DIR` |
| `src/mac/config_paths.py` | Resolves + seeds the runtime config folder (`config_dir`, `key_def_path`, `ensure_config_dir`) |
| `src/mac/github_update.py` | GitHub repo URL/constants (used for the "Open Project on GitHub" menu item) |
| `src/mac/login_item.py` | Start-at-login toggle — writes a RunAtLoad-only user LaunchAgent |
| `src/mac/watchdog.py` | Mac watchdog entry point |
| `src/mac/plugins/` | Plugin implementations (extend `BasePlugin`) |
| `src/mac/plugins_config/` | Plugin config `*.json.example` templates (seed source; real `*.json` git-ignored) |
| `src/mac/hooks/` | Claude Code hook scripts (`streamdeck-claude.py`) + installer |
| `src/mac/requirements.txt` | Mac Python dependencies |
| `src/mac/statusbar.py` | Menu-bar app (rumps wrapper around watchdog); status dot, Start-at-login, GitHub/About menu items |
| `src/mac/assets/grid_icon.png` | Menu bar icon — regenerate with `scripts/generate_icon.py` |
| `src/mac/assets/app_icon.icns` | Dock/Finder app icon — regenerate with `scripts/generate_app_icon.py` |
| `src/mac/layout_formatter.py` | Loads `key_def.json`, formats layout lines for the status bar cheat sheet |
| `scripts/generate_icon.py` | One-time generator for `src/mac/assets/grid_icon.png` |
| `scripts/generate_app_icon.py` | One-time generator for `src/mac/assets/app_icon.icns` (Dock/Finder icon) |
| `DIYStreamDeck.spec` | PyInstaller spec for the standalone `.app` bundle |
| `build-app.sh` | Builds `dist/DIYStreamDeck.app`; `--install` copies to `/Applications/` |
| `tests/` | Test suite (see [`tests/CLAUDE.md`](tests/CLAUDE.md)) |
| `CHANGELOG.md` | Change history |

## Development Commands

```bash
# Runtime venv setup (needs framework Python for rumps/menu bar)
# python.org Python 3.11 installer creates /Library/Frameworks/Python.framework/
# Homebrew Python is non-framework and works for everything except the statusbar app
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m venv .venv
.venv/bin/pip install -r src/mac/requirements.txt

# Run the menu-bar status app
./run-statusbar.sh

# Build the standalone .app (requires pyinstaller in .venv)
./build-app.sh [--install]

# Install dependencies
pip install -r src/mac/requirements.txt

# Run watchdog (launcher sets PYTHONPATH automatically)
./run-mac-watchdog.sh --port /dev/cu.usbmodem2101 --verbose

# Run directly
python3 src/mac/watchdog.py --port /dev/cu.usbmodem2101 --verbose

# Deploy Pico firmware / key_def.json — copy onto the CIRCUITPY drive.
# Use Thonny (save code.py to the Pico + Ctrl-D in the REPL), or drag the files
# onto /Volumes/CIRCUITPY in Finder. Note: if the Pico's boot.py does
# storage.remount("/", readonly=False), CIRCUITPY is read-only to the host and
# only Thonny/REPL can write — remove that boot.py to enable host-side copies.

# Manually trigger a Claude Code signal without waiting for a real event
./test-claude.sh                 # cycles green → red → yellow
```

For serial-protocol debugging: run watchdog with `--verbose` (logs `Active app:`, `[Pico] <text>` output, plugin activity) and use `send_output(text)` on the Pico to correlate events across the wire.

`send_output(text)` writes `Output: <text>\n` to the Mac console (via the watchdog); `print(text)` on the Pico only shows in a directly-attached serial REPL (Thonny) and is invisible to the running watchdog.

### Testing

```bash
# First-time setup (use Python 3.11 — Python 3.14 has an importlib.metadata bug that causes pytest to hang on startup)
/opt/homebrew/bin/python3.11 -m venv test_venv && source test_venv/bin/activate
pip install -r tests/requirements_test.txt

# Run tests
./run-tests.sh all       # everything (389 tests)
./run-tests.sh pico      # Pi Pico only
./run-tests.sh mac       # Mac/watchdog only
./run-tests.sh security  # security tests only
```

## TDD Workflow

For every bug fix or new feature:

1. Write a failing test targeting the exact behaviour
2. Confirm it fails: `./run-tests.sh all`
3. Apply the minimal fix
4. Confirm all tests pass: `./run-tests.sh all`
5. Update `CHANGELOG.md`

Test locations:

| Change area | Test file |
| --- | --- |
| Pi Pico / `code.py` | `tests/unit/pico/` |
| Mac plugin | `tests/unit/mac/plugins/test_<plugin>.py` |
| Watchdog | `tests/unit/mac/test_watchdog.py` |
| Security | `tests/security/` |

## Plugin Development

Plugins extend `BasePlugin` in `src/mac/plugins/`. Each plugin needs a config template in `src/mac/plugins_config/<name>.json.example` (seeded into the runtime folder on first run). At runtime, `load_plugins` looks for an active `<name>.json` first in `~/Documents/DIYStreamDeck/` (flat, `STREAMDECK_CONFIG_DIR` override), then the in-repo `plugins_config/`, then `~/Library/Application Support/DIYStreamDeck/plugins_config/`. Command format: `plugin_name.command [parameter]`. See [README.md](README.md) for the full command reference.

Service-style plugins (that push events *to* the keypad, not just react to keypresses) override optional `on_watchdog_start(send_to_keypad)` and `on_watchdog_stop()` on `BasePlugin` — the `on_watchdog_` prefix keeps lifecycle names distinct from user command handlers like `SoundsPlugin.stop`. See `src/mac/plugins/claude.py` for the reference implementation (Unix-socket listener relaying `Claude: <color>` to the Pico).

## Gotchas

- **Homebrew Python + rumps**: Homebrew Python is non-framework. `rumps` status bar items need `title=" "` (a space, not `None`) alongside `icon=` or the item is invisible. `title=None` + icon renders nothing.
- **`redis` hangs Python**: A broken `redis` install causes Python (and `pip`) to hang on import. Remove it directly: `rm -rf .venv/lib/python3.11/site-packages/redis .venv/lib/python3.11/site-packages/redis-*.dist-info`
- **PyObjC NSRect format**: `((x, y), (w, h))` — not `(x, y, w, h)`. The flat 4-tuple raises `ValueError: depythonifying struct of 2 members`.
- **Plugin loader order**: Config check must happen before module import (`load_plugins` in `watchdog.py`). Importing first causes noisy errors from unconfigured plugins whose optional dependencies (e.g. `spotipy` → `redis`) are missing.
- **iCloud-synced repo invalidates ad-hoc `.app` signatures**: this repo lives under an iCloud-synced `~/Documents`; the file provider stamps `com.apple.fileprovider.fpfs#P`/`FinderInfo` xattrs on the freshly-signed bundle, so `codesign --verify` fails seconds later (the app still runs). For a valid signature build/run from a non-synced path — `build-app.sh --install` re-signs the `/Applications` copy.
- **PyInstaller `.app` signing needs two passes**: its internal ad-hoc sign fails on resource-fork detritus, and the first `xattr -cr` + `codesign` still trips `--verify`; a second pass fixes it (`sign_app` loop in `build-app.sh`). A stale `build/` causes `struct.error: unpack requires a buffer of 4 bytes` — `build-app.sh` does `rm -rf build dist` first.
- **PyInstaller entry-script `__file__` = bundle root**: `statusbar.py` (the entry script) sees `__file__` under `sys._MEIPASS`, not `src/mac` — resolve bundled resources via `config_paths.bundle_root()`. Dotted submodules (e.g. `src.mac.watchdog`) keep a correct `__file__`.
- **One PyInstaller build at a time**: two concurrent `build-app.sh` runs (e.g. a background build + a terminal build) corrupt the shared cache and crash with `FileNotFoundError: index.dat`. If it happens, `rm -rf "$HOME/Library/Application Support/pyinstaller"` and rebuild solo.
- **rumps has no colored-text API**: colored menu text (status dot, layout dots) is set via `item._menuitem.setAttributedTitle_(NSMutableAttributedString)` — see `statusbar._set_dot_title`. Always also set `item.title` (rumps keys its menu dict by title, so empty titles collide).
- **CIRCUITPY read-only + stale cache**: a Pico `boot.py` with `storage.remount("/", readonly=False)` gives the Pico write access and mounts CIRCUITPY read-only on the host (even root gets `Operation not permitted`) — deploy `code.py`/`key_def.json` with **Thonny**. A read-only mount also serves stale cached bytes after a Pico-side write; `diskutil unmount /dev/diskNsM && diskutil mount /dev/diskNsM` to re-read. (macOS 26's FSKit `msdos` also breaks `mount -o noasync -t msdos`.)

## Development Principles

- **KISS** — simple over clever
- **YAGNI** — no speculative features
- **DRY** — shared helpers over duplication
- **Security first** — validate all inputs and file paths at system boundaries
