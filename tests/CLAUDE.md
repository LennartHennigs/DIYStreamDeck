# StreamDeck Testing Framework - Claude Code Guide

## Overview

This testing framework provides comprehensive test coverage for the StreamDeck project, including unit tests for both Pi Pico (CircuitPython) and macOS components, plus security vulnerability testing.

## Quick Commands

```bash
# Activate virtual environment
source test_venv/bin/activate

# Run all tests
./run-tests.sh all

# Common pytest commands
pytest tests/unit/ -m "not slow" --tb=line -q       # Quick unit tests
pytest tests/unit/ -v                               # Unit tests verbose
pytest tests/security/ -m security -v               # Security vulnerability tests
pytest tests/ -v                                    # All tests verbose
```

## Architecture

### Directory Structure

```text
tests/
├── conftest.py                    # Shared pytest fixtures + helpers (wait_for, short_socket_path)
├── pytest.ini                     # Pytest configuration
├── requirements_test.txt          # Test dependencies
├── security/                      # Security vulnerability tests
│   ├── test_actual_vulnerabilities.py
│   └── test_command_injection.py
└── unit/                          # Unit tests
    ├── mac/
    │   ├── test_watchdog.py
    │   ├── test_statusbar_layout.py
    │   ├── hooks/
    │   │   ├── test_streamdeck_claude.py
    │   │   └── test_install_claude_hooks.py
    │   └── plugins/
    │       ├── test_base_plugin_lifecycle.py
    │       ├── test_claude_plugin.py
    │       ├── test_hue_plugin.py
    │       ├── test_load_plugins_config.py
    │       ├── test_sounds_plugin.py
    │       └── test_spotify.py
    └── pico/
        ├── conftest.py
        ├── mock_circuitpython.py
        ├── test_config_loader.py
        ├── test_flash_handler.py
        ├── test_heartbeat_functionality.py
        ├── test_json_corruption.py
        ├── test_key_controller.py
        └── test_keypad_functionality.py
```

### Mock System

The testing framework uses mocking within individual test files for isolation:

- Tests use `Mock()` and `MagicMock()` directly for complete isolation
- No external dependencies or hardware access required
- Plugin tests mock API clients (`spotipy`, `phue`, etc.) locally
- Pi Pico tests use `mock_circuitpython.py` to simulate all CircuitPython hardware APIs

## Test Categories

### Unit Tests

- **Pi Pico Tests**: Configuration loading, JSON parsing, keypad setup, heartbeat + timeout, key rotation, folder navigation, JSON corruption handling, string key type, eager config validation, `Claude:` handler (sticky signal color), `Output:` protocol
- **Mac Plugin Tests**: Hue light control, Spotify integration, sounds playback, command handling, error scenarios
- **Mac Plugin Tests (claude)**: Socket listener lifecycle, color validation, `on_watchdog_start/stop` behavior, keypad-triggerable test commands
- **Mac Hook Tests**: Claude Code hook script (`streamdeck-claude.py`) event routing + silent-on-failure; `install-claude-hooks.sh` idempotency, backup, uninstaller preserves other hooks
- **Watchdog Tests**: Source-level checks for VERSION interpolation, dead code, and type annotations; `App:` deduplication; plugin lifecycle wiring
- **BasePlugin Lifecycle Tests**: `on_watchdog_start` / `on_watchdog_stop` are optional no-op defaults; existing plugins unaffected
- **Mock-based**: Complete isolation from hardware dependencies

### Security Tests

- **Command Injection**: Tests for shell command vulnerabilities
- **Path Traversal**: File access security validation
- **Input Validation**: Parameter sanitization checks
- **JSON Safety**: Secure JSON parsing validation

## Development Workflow

### Adding New Tests

Follow TDD: write the failing test first, confirm it fails, then apply the fix.

```bash
# Mac plugin test
tests/unit/mac/plugins/test_newplugin.py

# Pi Pico functionality test
tests/unit/pico/test_newfeature.py

# Security test
tests/security/test_new_vulnerability.py
```

Use fixtures from `conftest.py` where available (`mock_config`, `temp_file`, `mock_hue_bridge`, `mock_spotify_client`, etc.).

### Reusable helpers

- `_make_watchdog(serial_mock, verbose)` in `tests/unit/mac/test_watchdog.py` — instantiates a `WatchDog` bypassing Cocoa init. Reuse for any watchdog method test.
- `_read_source()` in `tests/unit/mac/test_watchdog.py` — for source-inspection tests (guard against structural regressions like symbol removal).
- `wait_for(condition, timeout, interval)` in `tests/conftest.py` — poll a predicate; used by claude-plugin socket tests.
- `short_socket_path` fixture in `tests/conftest.py` — yields an `AF_UNIX` path under `/tmp` short enough for macOS's ~104-char limit (pytest's `tmp_path` is too deep).

### Test Markers

Available pytest markers in `pytest.ini`:

- `@pytest.mark.slow` — Skip in quick tests
- `@pytest.mark.security` — Security-focused tests
- `@pytest.mark.mac_only` — macOS-specific tests
- `@pytest.mark.pico_only` — Pi Pico-specific tests

## Common Issues & Solutions

**Import errors** — Install dependencies: `pip install -r tests/requirements_test.txt`

**Test discovery issues** — Ensure `__init__.py` files exist and `PYTHONPATH` includes project root

**Mock assertion failures** — Verify mock method names match actual implementation

**Virtual environment** — Always activate first: `source test_venv/bin/activate`

**Suite speed** — the full suite runs in ~1–2 s. Pico tests never real-sleep: the autouse `fast_sleep` fixture in `tests/unit/pico/conftest.py` caps `time.sleep` at 1 ms (the firmware's HID-timing sleeps are meaningless in unit tests, and macOS App Nap defers real sleeps of *backgrounded* pytest runs for minutes — never remove that fixture). If a run looks hung, it is almost certainly running as a background/App-Napped process — run pytest in a foreground terminal.

## Testing Principles

1. **Isolation**: Each test runs independently with fresh mocks
2. **Realistic**: Mocks simulate actual hardware/API behavior patterns
3. **Comprehensive**: Cover both success and failure scenarios
4. **Security-First**: Include vulnerability testing as a core requirement
5. **Fast**: Quick feedback loop for development
