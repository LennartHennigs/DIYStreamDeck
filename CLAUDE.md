# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

DIY StreamDeck using a Raspberry Pi Pico + Pimoroni RGB Keypad. Two components:

- **Pi Pico** (`src/pi_pico/`): CircuitPython (`code.py`, `KeyController` class) — reads `key_def.json`, drives LEDs, sends HID events.
  **`code.py` is CircuitPython, not CPython.** Constraints: no `threading`, no `.with_traceback()`, no `json.JSONDecodeError` (raises plain `ValueError`), no `errno` module, ~200 KB heap. Keep changes minimal — every extra import and line costs RAM.
- **Mac Watchdog** (`src/mac/`): Python (`watchdog.py`, `WatchDog` class) — detects active app via Cocoa/NSWorkspace, sends app name to Pico over USB serial, executes plugin commands

### Communication Protocol

| Message | Direction | Purpose |
| --- | --- | --- |
| `HELLO` / `BYE` | Mac → Pico | Startup/shutdown handshake |
| `HB` | Mac → Pico | Heartbeat (connection keepalive) |
| `App:<name>` | Mac → Pico | Active application changed |
| `ECHO` | Mac → Pico | Lightweight connection test |

Pico unloads the keypad if heartbeats stop (host disconnected).

## Key Configuration (`key_def.json`)

Four top-level sections: `settings`, `applications`, `folders`, `urls`.

Key types: **shortcut** (`key_sequence`), **app launch** (`application`), **folder** (`folder`), **action** (`action`).

Special app entries: `_default` (merged into every layout), `_otherwise` (fallback for unknown apps).

## File Locations

| Path | Purpose |
| --- | --- |
| `src/pi_pico/key_def.json` | Key layout configuration |
| `src/mac/watchdog.py` | Mac watchdog entry point |
| `src/mac/plugins/` | Plugin implementations |
| `src/mac/plugins_config/` | Plugin credentials (git-ignored; copy from `*.json.example`) |
| `src/mac/sounds/` | Audio files for sounds plugin |
| `requirements/requirements_mac.txt` | Mac Python dependencies |

## Development Commands

```bash
# Install dependencies
pip install -r requirements/requirements_mac.txt

# Run watchdog (launcher sets PYTHONPATH automatically)
./run-mac-watchdog.sh --port /dev/cu.usbmodem2101 --verbose

# Run directly
python3 src/mac/watchdog.py --port /dev/cu.usbmodem2101 --verbose
```

### Testing

```bash
# First-time setup
python -m venv test_venv && source test_venv/bin/activate
pip install -r tests/requirements_test.txt

# Run tests
./run-tests.sh all       # everything (204 tests)
./run-tests.sh pico      # Pi Pico only
./run-tests.sh mac       # Mac/watchdog only
./run-tests.sh security  # security tests only
```

See [`tests/CLAUDE.md`](tests/CLAUDE.md) for mock framework details.

## Plugin System

Plugins extend `BasePlugin` in `src/mac/plugins/`. Config templates in `src/mac/plugins_config/*.json.example`.

Command format: `plugin_name.command [parameter]`
Examples: `spotify.next`, `hue.toggle 'Lamp Name'`, `sounds.play 'file.mp3'`

| Plugin | Config file | Notes |
| --- | --- | --- |
| Spotify | `spotify.json` | Requires Premium account |
| Hue | `hue.json` | Press bridge button on first run |
| Sounds | `sounds.json` | `.wav` / `.mp3` files in `sounds/` |

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

## Development Principles

- **KISS** — simple over clever
- **YAGNI** — no speculative features
- **DRY** — shared helpers over duplication
- **Security first** — validate all inputs and file paths at system boundaries

## Notes

- Watchdog requires macOS (Cocoa frameworks)
- Serial port is typically `/dev/cu.usbmodem*`
- `_default` keys merge into every app layout unless `ignore_default: true`
- `_otherwise` is the fallback layout for apps with no explicit definition
