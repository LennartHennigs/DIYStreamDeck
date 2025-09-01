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

# Run watchdog script
python3 src/mac/watchdog.py --port /dev/cu.usbmodem2101 --verbose

# Run with rotation support
python3 src/mac/watchdog.py --port /dev/cu.usbmodem2101 --rotate CCW --verbose
```

### Pi Pico Development
- Install CircuitPython on Pi Pico
- Copy `src/pi_pico/` contents to Pi Pico root
- Edit `key_def.json` to configure key layouts
- Use Thonny IDE for CircuitPython development

## Plugin System

Plugins are located in `src/mac/plugins/` and extend `BasePlugin`:

### Available Plugins
- **Spotify**: Music control (requires API credentials in `config/spotify.json`)
- **Hue**: Philips Hue light control (requires bridge IP in `config/hue.json`)
- **Sounds**: Audio playback for `.wav` and `.mp3` files

### Plugin Commands
- Format: `plugin_name.command [parameter]`
- Examples: `spotify.next`, `hue.toggle 'Lamp Name'`, `sounds.play 'file.mp3'`

## Important File Locations

- **Main Config**: `src/pi_pico/key_def.json` - Primary key layout configuration
- **Mac Dependencies**: `requirements/requirements_mac.txt` - Python package requirements
- **Plugin Configs**: `arc/mac/plugins_config/` - Individual plugin configuration files
- **Sounds**: `src/mac/sounds/` - Audio files for sound plugin

## Development Principles

When working with this codebase, follow these core principles:

- **KISS (Keep It Simple, Stupid)**: Favor simple, straightforward solutions over complex abstractions
- **YAGNI (You Aren't Gonna Need It)**: Don't add features or complexity until they are actually needed
- **DRY (Don't Repeat Yourself)**: Eliminate code duplication through reusable functions and shared configuration

## Development Notes

- The watchdog script requires macOS-specific Cocoa frameworks
- Serial port typically appears as `/dev/cu.usbmodem*` on macOS
- Key rotation settings accommodate different physical orientations
- Global `_default` key definitions apply to all applications unless `ignore_default: true`
- The `_otherwise` section provides fallback keys for undefined applications
