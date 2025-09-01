# StreamDeck Testing Framework - Claude Code Guide

## Overview

This testing framework provides comprehensive test coverage for the StreamDeck project, including unit tests for both Pi Pico (CircuitPython) and macOS components, plus security vulnerability testing.

## Quick Commands

```bash
# Activate virtual environment
source test_venv/bin/activate

# Common test commands
pytest tests/unit/ -m "not slow" --tb=line -q       # Quick unit tests
pytest tests/unit/ -v                              # Unit tests verbose  
pytest tests/security/ -m security -v               # Security vulnerability tests
pytest tests/ -v                                    # All tests verbose
```

## Architecture

### Directory Structure
```
tests/
├── conftest.py              # Shared pytest fixtures (ESSENTIAL)
├── pytest.ini             # Pytest configuration
├── requirements_test.txt   # Test dependencies
├── security/               # Security vulnerability tests
│   └── test_command_injection.py
└── unit/                   # Unit tests
    ├── mac/plugins/        # macOS plugin tests
    │   └── test_spotify.py
    └── pico/              # Pi Pico tests
        └── test_config_loader.py
```

### Mock System

The testing framework uses mocking within individual test files for isolation:

**Test-Level Mocks** (within each test file):
- Tests use `Mock()` and `MagicMock()` directly for complete isolation
- No external dependencies or hardware access required
- Plugin tests mock API clients (`spotipy`, `phue`, etc.) locally

## Test Categories

### Unit Tests (31 tests passing)
- **Pi Pico Tests**: Configuration loading, JSON parsing, keypad setup
- **Mac Plugin Tests**: Spotify integration, command handling, error scenarios
- **Mock-based**: Complete isolation from hardware dependencies

### Security Tests (4 passing, 5 expected failures)
- **Command Injection**: Tests for shell command vulnerabilities
- **Path Traversal**: File access security validation
- **Input Validation**: Parameter sanitization checks
- **JSON Safety**: Secure JSON parsing validation

> **Note**: Security test "failures" are intentional - they demonstrate actual vulnerabilities in the codebase that need fixing.

## Development Workflow

### Adding New Tests

1. **Unit Tests**: Add to appropriate platform directory
   ```bash
   # Mac plugin test
   tests/unit/mac/plugins/test_newplugin.py
   
   # Pi Pico functionality test  
   tests/unit/pico/test_newfeature.py
   ```

2. **Security Tests**: Add to security directory
   ```bash
   tests/security/test_new_vulnerability.py
   ```

3. **Use Fixtures**: Leverage shared fixtures from `conftest.py`
   ```python
   def test_my_feature(mock_config, temp_file):
       # Test implementation
   ```

### Running Tests

```bash
# Quick development cycle
pytest tests/unit/ -m "not slow" --tb=line -q

# Full unit tests with verbose output
pytest tests/unit/ -v

# Security vulnerability assessment
pytest tests/security/ -m security -v

# All tests (unit + security)
pytest tests/ -v
```

### Test Markers

Available pytest markers in `pytest.ini`:
- `@pytest.mark.slow` - Skip in quick tests
- `@pytest.mark.security` - Security-focused tests
- `@pytest.mark.mac_only` - macOS-specific tests
- `@pytest.mark.pico_only` - Pi Pico-specific tests

## Key Insights

### Mocking Strategy
The framework uses **complete mocking** rather than partial imports to achieve true unit test isolation. This prevents dependency issues and allows testing without hardware.

### Security Testing Approach
Security tests deliberately use **vulnerable implementations alongside secure versions** to validate that security measures work correctly.

### Configuration Testing
Tests validate both **happy path scenarios and edge cases** including malformed JSON, missing files, and invalid configurations.

### Plugin Architecture Testing
Plugin tests use **behavioral mocking** that simulates actual API responses and error conditions for realistic testing scenarios.

## Common Issues & Solutions

### Import Errors
**Problem**: `ModuleNotFoundError` for external dependencies
**Solution**: Install test dependencies: `pip install -r tests/requirements_test.txt`

### Test Discovery Issues
**Problem**: Pytest not finding tests
**Solution**: Ensure `__init__.py` files exist and `PYTHONPATH` includes project root

### Mock Assertion Failures
**Problem**: `AssertionError: Expected 'method' to have been called`
**Solution**: Verify mock method names match actual implementation

### Virtual Environment
**Problem**: Dependencies not found
**Solution**: Always activate test virtual environment first:
```bash
source test_venv/bin/activate
pip install -r tests/requirements_test.txt
```

## Testing Principles

1. **Isolation**: Each test runs independently with fresh mocks
2. **Realistic**: Mocks simulate actual hardware/API behavior patterns
3. **Comprehensive**: Cover both success and failure scenarios
4. **Security-First**: Include vulnerability testing as core requirement
5. **Fast**: Quick feedback loop for development

## Future Enhancements

- **Performance Tests**: Add benchmark tests for key operations
- **Integration Tests**: Add end-to-end workflow testing
- **Hardware Tests**: Add optional real hardware validation
- **Visual Testing**: Add UI/LED pattern validation tests

---

*This testing framework supports the StreamDeck project's goal of providing reliable, secure hardware control with comprehensive validation.*