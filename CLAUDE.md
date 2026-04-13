# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a DIY StreamDeck project that uses a Raspberry Pi Pico and Pimoroni RGB Keypad to create dynamic app-specific shortcut keys. The system consists of two main components:

1. **Pi Pico Controller** (`src/pi_pico/`): CircuitPython code that runs on the hardware
2. **Mac Watchdog** (`src/mac/`): Python script that monitors active applications and sends commands to the Pi Pico

## Architecture

### Hardware Components
- **Pi Pico** runs `code.py` (CircuitPython) with the `KeyController` class
- **RGB Keypad** provides 16 programmable keys with LED feedback
- **USB Serial** connection between Pi Pico and Mac for communication

### Software Flow
1. **Watchdog** (`watchdog.py`) monitors active Mac applications using Cocoa frameworks
2. **Application Detection**: Sends app names to Pi Pico via serial when apps change focus
3. **Key Configuration**: Pi Pico loads appropriate key mappings from `key_def.json`
4. **Plugin System**: Watchdog handles plugin commands (Spotify, Hue lights, sound playback)

### Communication Protocol
- **HELLO/BYE Messages**: Startup and shutdown handshake with version information
- **Heartbeat System**: Regular "HB" messages to detect connection status
- **Echo Diagnostics**: Lightweight connection testing with ECHO commands
- **Timeout Detection**: Pi Pico automatically unloads keypad if host disconnects

### Key Architecture Components

#### Pi Pico (`src/pi_pico/code.py`)
- `KeyController` class manages all keypad functionality
- Loads configuration from `key_def.json`
- Handles key press/release events and LED management
- Supports key rotation (CW/CCW) for different orientations
- Manages folder navigation and hierarchical key layouts

#### Mac Watchdog (`src/mac/watchdog.py`)
- `WatchDog` class extends `Cocoa.NSObject` for system integration
- Monitors application focus changes using NSWorkspace notifications
- Handles plugin command execution through modular plugin system
- Supports URL detection for browser-specific shortcuts

## Configuration System

### Key Definition Structure (`key_def.json`)
- **Applications**: App-specific key mappings
- **Folders**: Hierarchical key groupings
- **URLs**: Browser URL-specific shortcuts
- **Settings**: Global configuration (rotation, etc.)

### Key Types
- **Shortcut Keys**: Execute keyboard combinations
- **Application Keys**: Launch/focus applications
- **Folder Keys**: Navigate to sub-menus
- **Action Keys**: Trigger plugin commands or special actions

## Development Commands

### Mac Development
```bash
# Install Python dependencies
pip install -r requirements/requirements_mac.txt

# Run watchdog script using the launcher (recommended)
./run-mac-watchdog.sh --port /dev/cu.usbmodem2101 --verbose

# Run directly with Python
python3 src/mac/watchdog.py --port /dev/cu.usbmodem2101 --verbose

# Run with rotation support
python3 src/mac/watchdog.py --port /dev/cu.usbmodem2101 --rotate CCW --verbose
```

### Testing

```bash
./run-tests.sh all        # All tests (150+ tests)
./run-tests.sh pico       # Pi Pico tests only
./run-tests.sh mac        # Mac watchdog tests
./run-tests.sh security   # Security vulnerability tests
./run-tests.sh quick      # Fast subset

# Setup test environment (first time)
python -m venv test_venv
source test_venv/bin/activate
pip install -r tests/requirements_test.txt
```

See `tests/CLAUDE.md` for full test category details and mock framework documentation.

### Pi Pico Development
- Install CircuitPython on Pi Pico
- Copy `src/pi_pico/` contents to Pi Pico root
- Edit `key_def.json` to configure key layouts
- Use Thonny IDE for CircuitPython development

## Plugin System

Plugins are located in `src/mac/plugins/` and extend `BasePlugin`:

- **Spotify**: Music control — credentials in `src/mac/plugins_config/spotify.json` (copy from `spotify.json.example`)
- **Hue**: Philips Hue light control — bridge IP in `src/mac/plugins_config/hue.json` (copy from `hue.json.example`)
- **Sounds**: Audio playback for `.wav` and `.mp3` files

Plugin command format: `plugin_name.command [parameter]`
Examples: `spotify.next`, `hue.toggle 'Lamp Name'`, `sounds.play 'file.mp3'`

## Important File Locations

- **Main Config**: `src/pi_pico/key_def.json` — Primary key layout configuration
- **Mac Dependencies**: `requirements/requirements_mac.txt` — Python package requirements
- **Plugin Configs**: `src/mac/plugins_config/` — Individual plugin configuration files (git-ignored; use `*.json.example` templates)
- **Sounds**: `src/mac/sounds/` — Audio files for sound plugin

## TDD Workflow

For every bug fix or new feature:

1. **Write a failing test first** targeting the exact behaviour to fix
2. **Confirm it fails**: `./run-tests.sh all`
3. **Apply the minimal fix**
4. **Confirm all tests pass**: `./run-tests.sh all`
5. **Update CHANGELOG.md** with a brief entry

New tests go in the matching location:

| Change area | Test location |
| --- | --- |
| Pi Pico / `code.py` | `tests/unit/pico/` |
| Mac plugin | `tests/unit/mac/plugins/test_<plugin>.py` |
| Watchdog | `tests/unit/mac/test_watchdog.py` |
| Security | `tests/security/` |

## Development Principles

- **KISS**: Favor simple, straightforward solutions over complex abstractions
- **YAGNI**: Don't add features or complexity until actually needed
- **DRY**: Eliminate duplication through reusable functions and shared configuration
- **Security First**: All user inputs and file operations must be validated and secured

## Development Notes

- The watchdog script requires macOS-specific Cocoa frameworks
- Serial port typically appears as `/dev/cu.usbmodem*` on macOS
- Key rotation settings accommodate different physical orientations
- Global `_default` key definitions apply to all applications unless `ignore_default: true`
- The `_otherwise` section provides fallback keys for undefined applications
