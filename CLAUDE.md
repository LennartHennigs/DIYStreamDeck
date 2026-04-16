# CLAUDE.md

Guidance for Claude Code when working in this repository. See [README.md](README.md) for user-facing setup, configuration, and plugin documentation.

## Project Overview

DIY StreamDeck using a Raspberry Pi Pico + Pimoroni RGB Keypad. Two components:

- **Pi Pico** (`src/pi_pico/`): CircuitPython (`code.py`, `KeyController` class) — reads `key_def.json`, drives LEDs, sends HID events.
  **`code.py` is CircuitPython, not CPython.** Constraints: no `threading`, no `.with_traceback()`, no `json.JSONDecodeError` (raises plain `ValueError`), no `errno` module, ~200 KB heap. Keep changes minimal — every extra import and line costs RAM.
- **Mac Watchdog** (`src/mac/`): Python (`watchdog.py`, `WatchDog` class) — detects active app via Cocoa/NSWorkspace, sends app name to Pico over USB serial, executes plugin commands.

`_default` keys merge into every app, folder, and URL layout unless `ignore_default: true`. `_otherwise` is the fallback layout for apps without a specific definition.

### Communication Protocol

| Message | Direction | Purpose |
| --- | --- | --- |
| `HELLO:<version>` | Mac → Pico | Startup handshake |
| `BYE` | Mac → Pico | Shutdown handshake |
| `HB` | Mac → Pico | Heartbeat keepalive |
| `App: <name>` | Mac → Pico | Active application changed |
| `Rotate: CW\|CCW` | Mac → Pico | Rotate keypad layout |
| `Terminated: <name>` | Mac → Pico | App terminated (resets toggle state) |
| `Launch: <name>` | Pico → Mac | Request app launch |
| `Run: <plugin.cmd>` | Pico → Mac | Request plugin command |
| `ECHO[:<token>]` | Pico → Mac | Connection test (watchdog replies `ECHO-OK`) |
| `PING` | Mac → Pico | Port probe during auto-detection |
| `PONG` | Pico → Mac | Reply confirming Pico identity |

Pico unloads the keypad if heartbeats stop (host disconnected).

## File Locations

| Path | Purpose |
| --- | --- |
| `src/pi_pico/code.py` | Pico firmware (CircuitPython) |
| `src/pi_pico/key_def.json` | Key layout configuration |
| `src/mac/watchdog.py` | Mac watchdog entry point |
| `src/mac/plugins/` | Plugin implementations (extend `BasePlugin`) |
| `src/mac/plugins_config/` | Plugin credentials (git-ignored; copy from `*.json.example`) |
| `src/mac/requirements.txt` | Mac Python dependencies |
| `tests/` | Test suite (see [`tests/CLAUDE.md`](tests/CLAUDE.md)) |
| `CHANGELOG.md` | Change history |

## Development Commands

```bash
# Install dependencies
pip install -r src/mac/requirements.txt

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
./run-tests.sh all       # everything (218 tests)
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

Plugins extend `BasePlugin` in `src/mac/plugins/`. Each plugin needs a config template in `src/mac/plugins_config/<name>.json.example`. Command format: `plugin_name.command [parameter]`. See [README.md](README.md) for the full command reference.

## Development Principles

- **KISS** — simple over clever
- **YAGNI** — no speculative features
- **DRY** — shared helpers over duplication
- **Security first** — validate all inputs and file paths at system boundaries
