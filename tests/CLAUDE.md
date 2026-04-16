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

```text                    # Shared pytest fixtures (ESSENTIAL)
├── pytest.ini                    # Pytest configuration
├── requirements_test.txt          # Test dependencies
├── security/                      # Security vulnerability tests
│   ├── test_actual_vulnerabilities.py
│   └── test_command_injection.py
└── unit/                          # Unit tests
    ├── mac/
    │   ├── test_watchdog.py
    │   └── plugins/
    │       ├── test_hue_plugin.py
    │       ├── test_sounds_plugin.py
    │       └── test_spotify.py
    └── pico/
        ├── mock_circuitpython.py
        ├── test_config_loader.py
        ├── test_key_controller.py
        ├── test_heartbeat_functionality.py
        ├── test_json_corruption.py
        └── test_keypad_functionality.py
```

### Mock System

The testing framework uses mocking within individual test files for isolation:

- Tests use `Mock()` and `MagicMock()` directly for complete isolation
- No external dependencies or hardware access required
- Plugin tests mock API clients (`spotipy`, `phue`, etc.) locally
- Pi Pico tests use `mock_circuitpython.py` to simulate all CircuitPython hardware APIs

## Test Categories

### Unit Tests (218 tests passing)

- **Pi Pico Tests** (85+ tests): Configuration loading, JSON parsing, keypad setup, heartbeat, key rotation, folder navigation, JSON corruption handling
- **Mac Plugin Tests**: Hue light control, Spotify integration, sounds playback, command handling, error scenarios
- **Watchdog Tests**: Source-level checks for VERSION interpolation, dead code, and type annotations
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

## Testing Principles

1. **Isolation**: Each test runs independently with fresh mocks
2. **Realistic**: Mocks simulate actual hardware/API behavior patterns
3. **Comprehensive**: Cover both success and failure scenarios
4. **Security-First**: Include vulnerability testing as a core requirement
5. **Fast**: Quick feedback loop for development
