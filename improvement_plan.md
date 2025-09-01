# StreamDeck Improvement Plan

## Executive Summary

This document outlines a comprehensive improvement plan for the DIY StreamDeck project based on a thorough code analysis. The plan addresses critical security vulnerabilities, code quality issues, and architectural improvements while maintaining the project's functional integrity.

## Current State Analysis

### Strengths
- Clean separation between hardware (Pi Pico) and host system (Mac)
- Extensible plugin architecture
- Configuration-driven design
- Good use of CircuitPython and macOS Cocoa APIs

### Critical Issues
- **Security Vulnerabilities**: Command injection, insecure credential storage, path traversal risks
- **Code Quality**: Large classes, inconsistent error handling, missing input validation
- **Robustness**: Silent failures, no graceful degradation, resource leaks
- **Testing**: Zero test coverage, no validation framework

## Phase 1: Critical Security Fixes (Week 1-2)

### Priority: 🔴 P0 - Immediate Action Required

#### 1.1 Fix Command Injection Vulnerability

**File**: `src/mac/plugins/base_plugin.py:26`

**Current Code**:
```python
def _ping(self, ip: str) -> bool:
    return os.system(f"ping -c 1 -W 2 {ip} > /dev/null 2>&1") == 0   
```

**Secure Replacement**:
```python
def _ping(self, ip: str) -> bool:
    import ipaddress, subprocess
    try:
        # Validate IP format first
        ipaddress.ip_address(ip)
        result = subprocess.run(['ping', '-c', '1', '-W', '2', ip], 
                              capture_output=True, timeout=5)
        return result.returncode == 0
    except (ValueError, subprocess.TimeoutExpired):
        return False
```

**Impact**: Prevents arbitrary command execution through malicious IP parameters

#### 1.2 Secure Credential Management

**Current Issue**: Spotify API credentials stored in plain text in `src/mac/plugins/config/spotify.json`

**Solution**: Implement secure credential storage using macOS Keychain

```python
import keyring

class SecureConfigLoader:
    def load_spotify_credentials(self):
        return {
            'client_id': keyring.get_password('streamdeck', 'spotify_client_id'),
            'client_secret': keyring.get_password('streamdeck', 'spotify_client_secret'),
            'redirect_uri': 'http://localhost:8888/callback'
        }
```

**Setup Commands**:
```bash
# Store credentials securely
security add-generic-password -a "streamdeck" -s "spotify_client_id" -w "your_client_id"
security add-generic-password -a "streamdeck" -s "spotify_client_secret" -w "your_client_secret"
```

#### 1.3 Path Traversal Protection

**File**: `src/mac/plugins/sounds.py:46`

**Current Code**:
```python
full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.sound_path, filename)
```

**Secure Implementation**:
```python
def _validate_and_resolve_path(self, filename: str) -> str:
    # Sanitize filename
    if '..' in filename or filename.startswith('/') or '\\' in filename:
        raise ValueError(f"Invalid filename: {filename}")
    
    filename = os.path.basename(filename)  # Remove any path components
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, self.sound_path, filename)
    
    # Ensure resolved path is within allowed directory
    if not os.path.realpath(full_path).startswith(os.path.realpath(base_dir)):
        raise ValueError(f"Path traversal attempt: {filename}")
    
    return full_path
```

## Phase 2: Code Quality & Architecture (Week 3-5)

### Priority: 🟡 P1 - High Impact

#### 2.1 Refactor KeyController Class

**Current Issue**: Single class with 447 lines handling multiple responsibilities

**Solution**: Split into focused components

```python
# src/pi_pico/keyboard_handler.py
class KeyboardHandler:
    """Handles key press/release events and HID communication"""
    
    def handle_key_press(self, key_number: int, key_config: dict):
        pass
    
    def handle_key_release(self, key_number: int, key_config: dict):
        pass

# src/pi_pico/configuration_manager.py
class ConfigurationManager:
    """Loads and validates JSON configuration"""
    
    def load_config(self, filename: str) -> dict:
        pass
    
    def validate_config(self, config: dict) -> bool:
        pass

# src/pi_pico/layout_manager.py
class LayoutManager:
    """Manages key layouts, folders, and rotations"""
    
    def apply_rotation(self, config: dict, rotation: str) -> dict:
        pass
    
    def open_folder(self, folder_name: str):
        pass

# src/pi_pico/serial_communicator.py
class SerialCommunicator:
    """Handles serial communication with host"""
    
    def read_command(self) -> str:
        pass
    
    def send_response(self, message: str):
        pass
```

#### 2.2 Implement Standardized Error Handling

**Create Error Hierarchy**:
```python
# src/common/exceptions.py
class StreamDeckError(Exception):
    """Base exception for StreamDeck operations"""
    pass

class ConfigurationError(StreamDeckError):
    """Configuration-related errors"""
    pass

class PluginError(StreamDeckError):
    """Plugin execution errors"""
    pass

class SerialCommunicationError(StreamDeckError):
    """Serial communication errors"""
    pass
```

**Implement Consistent Error Handling**:
```python
import logging

logger = logging.getLogger(__name__)

def execute_plugin_command(self, command: str):
    try:
        # Execute plugin command
        result = self._execute_command(command)
        return result
    except PluginError as e:
        logger.error(f"Plugin execution failed: {e}")
        # Provide user feedback through LED color or status
        self.indicate_error()
        return None
    except Exception as e:
        logger.error(f"Unexpected error in plugin execution: {e}")
        raise PluginError(f"Plugin command failed: {command}") from e
```

#### 2.3 Add Configuration Validation

**JSON Schema Definition**:
```python
# src/common/config_schema.py
KEYDEF_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "StreamDeck Key Definition",
    "type": "object",
    "properties": {
        "settings": {
            "type": "object",
            "properties": {
                "rotate": {"enum": ["CW", "CCW", ""]}
            }
        },
        "applications": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9._-]+$": {
                    "type": "object",
                    "patternProperties": {
                        "^(1[0-5]|[0-9])$": {  # Keys 0-15
                            "$ref": "#/definitions/keyDefinition"
                        }
                    }
                }
            }
        }
    },
    "definitions": {
        "keyDefinition": {
            "type": "object",
            "properties": {
                "key_sequence": {"oneOf": [{"type": "string"}, {"type": "array"}]},
                "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                "description": {"type": "string"},
                "application": {"type": "string"},
                "folder": {"type": "string"},
                "action": {"type": "string"}
            }
        }
    },
    "required": ["applications"]
}
```

**Validation Implementation**:
```python
import jsonschema

class ConfigValidator:
    def validate_config(self, config: dict) -> bool:
        try:
            jsonschema.validate(config, KEYDEF_SCHEMA)
            return True
        except jsonschema.ValidationError as e:
            raise ConfigurationError(f"Invalid configuration: {e.message}")
```

## Phase 3: Testing & Validation Framework (Week 6-7)

### Priority: 🟡 P1 - Foundation Building

#### 3.1 Unit Testing Infrastructure

**Test Framework Setup**:
```bash
# Install testing dependencies
pip install pytest pytest-cov pytest-mock

# Create test structure
mkdir -p tests/{unit,integration,hardware}
```

**Example Unit Tests**:
```python
# tests/unit/test_configuration_manager.py
import pytest
from src.pi_pico.configuration_manager import ConfigurationManager
from src.common.exceptions import ConfigurationError

class TestConfigurationManager:
    def test_valid_config_loading(self, tmp_path):
        config_file = tmp_path / "test_config.json"
        config_file.write_text('{"applications": {"test": {}}}')
        
        manager = ConfigurationManager()
        config = manager.load_config(str(config_file))
        
        assert "applications" in config
        assert "test" in config["applications"]
    
    def test_invalid_config_raises_error(self, tmp_path):
        config_file = tmp_path / "invalid.json"
        config_file.write_text('{"invalid": "json"')  # Missing closing brace
        
        manager = ConfigurationManager()
        
        with pytest.raises(ConfigurationError):
            manager.load_config(str(config_file))
    
    def test_keycode_conversion(self):
        manager = ConfigurationManager()
        result = manager.keycode_string_to_tuple("CTRL+A")
        
        assert isinstance(result, tuple)
        assert len(result) == 2
```

#### 3.2 Integration Testing

**Plugin System Testing**:
```python
# tests/integration/test_plugin_system.py
import pytest
from unittest.mock import Mock, patch
from src.mac.watchdog import WatchDog

class TestPluginSystem:
    def test_plugin_loading(self):
        watchdog = WatchDog()
        plugins = watchdog.load_plugins()
        
        assert 'spotify' in plugins
        assert 'hue' in plugins
        assert 'sounds' in plugins
    
    def test_plugin_command_execution(self):
        watchdog = WatchDog()
        
        with patch('src.mac.plugins.spotify.SpotifyPlugin.play') as mock_play:
            watchdog.execute_plugin_command('spotify.play')
            mock_play.assert_called_once()
```

#### 3.3 Hardware Testing Framework

**Serial Communication Testing**:
```python
# tests/hardware/test_serial_communication.py
import pytest
from unittest.mock import Mock
import serial

class TestSerialCommunication:
    def test_pi_pico_connection(self):
        # Test with mock serial connection
        mock_serial = Mock(spec=serial.Serial)
        mock_serial.readline.return_value = b"App: TestApp\n"
        
        # Test message parsing
        message = mock_serial.readline().decode().strip()
        assert message == "App: TestApp"
    
    @pytest.mark.hardware
    def test_real_hardware_connection(self):
        # Only run when hardware is connected
        try:
            ser = serial.Serial('/dev/cu.usbmodem2101', 9600, timeout=1)
            ser.write(b".\n")  # Send heartbeat
            response = ser.readline()
            ser.close()
            assert response is not None
        except serial.SerialException:
            pytest.skip("Hardware not connected")
```

#### 3.4 Configuration Validation Testing

```python
# tests/unit/test_config_validation.py
import pytest
from src.common.config_schema import ConfigValidator
from src.common.exceptions import ConfigurationError

class TestConfigValidation:
    def test_valid_config_passes_validation(self):
        valid_config = {
            "applications": {
                "test_app": {
                    "0": {
                        "key_sequence": "CTRL+A",
                        "color": "#FF0000",
                        "description": "Test key"
                    }
                }
            }
        }
        
        validator = ConfigValidator()
        assert validator.validate_config(valid_config) is True
    
    def test_invalid_color_format_fails(self):
        invalid_config = {
            "applications": {
                "test_app": {
                    "0": {
                        "color": "red"  # Invalid format, should be #RRGGBB
                    }
                }
            }
        }
        
        validator = ConfigValidator()
        
        with pytest.raises(ConfigurationError):
            validator.validate_config(invalid_config)
```

## Phase 4: Enhanced Features & Robustness (Week 8-10)

### Priority: 🟢 P2 - Enhancement

#### 4.1 Plugin Sandboxing and Health Monitoring

**Plugin Manager with Health Monitoring**:
```python
# src/mac/plugin_manager.py
import threading
import time
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Any] = {}
        self.plugin_health: Dict[str, str] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.health_monitor = threading.Thread(target=self._monitor_health, daemon=True)
        self.health_monitor.start()
    
    def execute_command_safely(self, command: str, timeout: int = 5):
        """Execute plugin command with timeout and error handling"""
        plugin_name = command.split('.')[0]
        
        try:
            future = self.executor.submit(self._execute_plugin_command, command)
            result = future.result(timeout=timeout)
            self.plugin_health[plugin_name] = "healthy"
            return result
        except TimeoutError:
            self.plugin_health[plugin_name] = f"timeout after {timeout}s"
            logger.warning(f"Plugin {plugin_name} timed out")
            return None
        except Exception as e:
            self.plugin_health[plugin_name] = f"error: {str(e)}"
            logger.error(f"Plugin {plugin_name} failed: {e}")
            return None
    
    def _monitor_health(self):
        """Background thread to monitor plugin health"""
        while True:
            for plugin_name, status in self.plugin_health.items():
                if status != "healthy":
                    logger.info(f"Plugin {plugin_name} status: {status}")
            time.sleep(30)  # Check every 30 seconds
```

#### 4.2 Configuration Hot-Reload

**File System Monitoring**:
```python
# src/common/config_watcher.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json

class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config_file: str, callback):
        self.config_file = config_file
        self.callback = callback
        self.last_modified = 0
    
    def on_modified(self, event):
        if event.src_path == self.config_file:
            # Debounce rapid file changes
            current_time = time.time()
            if current_time - self.last_modified > 1.0:
                try:
                    with open(self.config_file, 'r') as f:
                        new_config = json.load(f)
                    self.callback(new_config)
                    self.last_modified = current_time
                except Exception as e:
                    logger.error(f"Failed to reload config: {e}")

class ConfigWatcher:
    def __init__(self, config_file: str, callback):
        self.observer = Observer()
        self.observer.schedule(
            ConfigFileHandler(config_file, callback),
            path=os.path.dirname(config_file),
            recursive=False
        )
        self.observer.start()
    
    def stop(self):
        self.observer.stop()
        self.observer.join()
```

#### 4.3 Enhanced Error Recovery

**Automatic Recovery System**:
```python
# src/common/recovery_manager.py
class RecoveryManager:
    def __init__(self):
        self.backup_config = None
        self.connection_attempts = 0
        self.max_attempts = 5
    
    def create_config_backup(self, config: dict):
        """Create backup of working configuration"""
        self.backup_config = config.copy()
    
    def recover_from_config_error(self):
        """Restore from backup configuration"""
        if self.backup_config:
            logger.info("Restoring from backup configuration")
            return self.backup_config
        return None
    
    def handle_serial_disconnection(self):
        """Handle Pi Pico disconnection gracefully"""
        self.connection_attempts += 1
        
        if self.connection_attempts < self.max_attempts:
            logger.info(f"Attempting reconnection ({self.connection_attempts}/{self.max_attempts})")
            return self._attempt_reconnection()
        else:
            logger.error("Max reconnection attempts reached. Entering offline mode.")
            return self._enter_offline_mode()
    
    def _attempt_reconnection(self):
        # Try to reconnect to serial port
        available_ports = self._scan_serial_ports()
        for port in available_ports:
            if self._test_connection(port):
                logger.info(f"Reconnected on port {port}")
                self.connection_attempts = 0
                return port
        return None
    
    def _enter_offline_mode(self):
        """Graceful degradation when hardware unavailable"""
        logger.info("Entering offline mode - some features disabled")
        # Could still handle some plugin commands that don't require hardware
        return "offline"
```

## Phase 5: Documentation & Developer Experience (Week 11-12)

### Priority: 🟢 P2 - Long-term Sustainability

#### 5.1 Comprehensive API Documentation

**Enhanced Docstrings**:
```python
class KeyController:
    """
    Main controller for the StreamDeck RGB keypad functionality.
    
    This class manages the complete lifecycle of keypad operations including:
    - Loading and validating configuration files
    - Handling key press and release events
    - Managing LED states and colors
    - Processing serial commands from the host system
    - Coordinating folder navigation and key layouts
    
    The controller supports dynamic key layouts, application-specific mappings,
    and hierarchical folder structures for organizing shortcuts.
    
    Args:
        verbose (bool, optional): Enable detailed logging output. Defaults to False.
        config_file (str, optional): Path to JSON configuration file. 
                                   Defaults to "key_def.json".
    
    Raises:
        ConfigurationError: When the configuration file is missing, malformed,
                          or contains invalid key definitions.
        SerialError: When communication with the host system fails.
        
    Example:
        >>> controller = KeyController(verbose=True)
        >>> controller.run()  # Start main event loop
        
    Note:
        This class is designed to run on CircuitPython and requires specific
        hardware libraries (rgbkeypad, adafruit_hid).
    """
```

#### 5.2 Configuration Schema Documentation

**Complete Schema with Examples**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "StreamDeck Key Definition Schema",
  "description": "Complete configuration schema for StreamDeck key mappings",
  "version": "1.0.0",
  "type": "object",
  "examples": [
    {
      "settings": {
        "rotate": "CCW"
      },
      "applications": {
        "zoom.us": {
          "0": {
            "key_sequence": "GUI+SHIFT+A",
            "color": "#FFFF00",
            "description": "Mute/Unmute Audio"
          },
          "1": {
            "key_sequence": ["GUI", "SHIFT", "V"],
            "color": "#00FF00",
            "description": "Toggle Video"
          }
        }
      },
      "folders": {
        "apps_folder": {
          "0": {
            "application": "Spotify",
            "color": "#1DB954",
            "description": "Launch Spotify"
          },
          "15": {
            "action": "close_folder",
            "color": "#FFFFFF",
            "description": "Close Folder"
          }
        }
      }
    }
  ]
}
```

#### 5.3 Development Tools

**Configuration Validator CLI**:
```python
#!/usr/bin/env python3
# tools/validate_config.py

import argparse
import json
import sys
from src.common.config_schema import ConfigValidator

def main():
    parser = argparse.ArgumentParser(description='Validate StreamDeck configuration')
    parser.add_argument('config_file', help='Path to configuration JSON file')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose output')
    
    args = parser.parse_args()
    
    try:
        with open(args.config_file, 'r') as f:
            config = json.load(f)
        
        validator = ConfigValidator()
        if validator.validate_config(config):
            print(f"✅ Configuration file '{args.config_file}' is valid")
            
            if args.verbose:
                app_count = len(config.get('applications', {}))
                folder_count = len(config.get('folders', {}))
                print(f"📱 Found {app_count} applications")
                print(f"📁 Found {folder_count} folders")
            
            return 0
            
    except Exception as e:
        print(f"❌ Validation failed: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

**Plugin Template Generator**:
```python
#!/usr/bin/env python3
# tools/create_plugin.py

import argparse
import os
from pathlib import Path

PLUGIN_TEMPLATE = '''# StreamDeck Plugin: {plugin_name}
# Generated by create_plugin.py

import json
from typing import Dict, Callable, Any
from src.mac.plugins.base_plugin import BasePlugin

class {class_name}Plugin(BasePlugin):
    """
    {plugin_name} plugin for StreamDeck.
    
    This plugin provides {plugin_name} integration for the StreamDeck system.
    """
    
    def __init__(self, config_file: str, verbose: bool) -> None:
        self.verbose = verbose
        self.config = self._load_config(config_file)
    
    def commands(self) -> Dict[str, Callable]:
        """Return available commands for this plugin"""
        return {{
            '{plugin_name}.example_command': self.example_command,
        }}
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load plugin configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._log_and_raise(f"Failed to load config: {{e}}")
    
    def example_command(self) -> None:
        """Example command implementation"""
        if self.verbose:
            print("Executing {plugin_name} example command")
        # TODO: Implement your command logic here
        pass
'''

CONFIG_TEMPLATE = '''{{
    "example_setting": "default_value",
    "api_endpoint": "https://api.example.com",
    "timeout": 5
}}
'''

def main():
    parser = argparse.ArgumentParser(description='Generate a new StreamDeck plugin')
    parser.add_argument('plugin_name', help='Name of the plugin (e.g., "weather")')
    parser.add_argument('--output-dir', default='src/mac/plugins', 
                       help='Output directory for plugin files')
    
    args = parser.parse_args()
    
    plugin_name = args.plugin_name.lower()
    class_name = plugin_name.capitalize()
    output_dir = Path(args.output_dir)
    
    # Create plugin file
    plugin_file = output_dir / f"{plugin_name}.py"
    with open(plugin_file, 'w') as f:
        f.write(PLUGIN_TEMPLATE.format(
            plugin_name=plugin_name,
            class_name=class_name
        ))
    
    # Create config file
    config_dir = output_dir / "config"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / f"{plugin_name}.json"
    with open(config_file, 'w') as f:
        f.write(CONFIG_TEMPLATE)
    
    print(f"✅ Created plugin files:")
    print(f"   📄 {plugin_file}")
    print(f"   ⚙️  {config_file}")
    print(f"")
    print(f"Next steps:")
    print(f"1. Edit {plugin_file} to implement your plugin logic")
    print(f"2. Update {config_file} with your plugin configuration")
    print(f"3. Add your plugin commands to key_def.json")

if __name__ == '__main__':
    main()
```

## Implementation Priority Matrix

| Task | Security Impact | Development Effort | User Impact | Priority |
|------|----------------|-------------------|-------------|----------|
| Fix command injection | Critical | Low | Medium | 🔴 P0 |
| Secure credential storage | High | Medium | Low | 🔴 P0 |
| Add input validation | High | Medium | Medium | 🔴 P0 |
| Refactor KeyController | Low | High | High | 🟡 P1 |
| Add unit tests | Medium | High | Low | 🟡 P1 |
| Configuration validation | Medium | Medium | High | 🟡 P1 |
| Plugin health monitoring | Medium | Medium | Medium | 🟡 P1 |
| Configuration hot-reload | Low | Medium | High | 🟢 P2 |
| Plugin sandboxing | Medium | High | Low | 🟢 P2 |
| Development tools | Low | Medium | Medium | 🟢 P2 |

## Success Metrics

### Security Metrics
- [ ] Zero command injection vulnerabilities (static analysis + penetration testing)
- [ ] All API credentials stored in secure storage (Keychain/environment variables)
- [ ] Input validation implemented for all user-controlled data
- [ ] Security audit completed with no critical findings

### Code Quality Metrics
- [ ] Test coverage > 80% (unit + integration tests)
- [ ] Cyclomatic complexity < 10 per method
- [ ] All classes follow Single Responsibility Principle (< 200 lines per class)
- [ ] Zero critical code smells (SonarQube or similar analysis)
- [ ] Type hints coverage > 90%

### Reliability Metrics
- [ ] Plugin failure doesn't crash main system (isolation testing)
- [ ] System recovers gracefully from hardware disconnection
- [ ] Configuration errors provide actionable error messages
- [ ] System uptime > 99% during normal operation
- [ ] Zero memory leaks during extended operation

### Developer Experience Metrics
- [ ] Complete API documentation (100% docstring coverage)
- [ ] Plugin development guide with working examples
- [ ] Automated testing pipeline (CI/CD setup)
- [ ] Configuration validation tools available
- [ ] Plugin template generator functional

## Risk Assessment

### High Risk Items
1. **Plugin System Refactoring**: Risk of breaking existing functionality
   - *Mitigation*: Comprehensive integration tests before refactoring
   
2. **Serial Communication Changes**: Risk of hardware compatibility issues
   - *Mitigation*: Maintain backward compatibility, extensive hardware testing

3. **Configuration Schema Changes**: Risk of breaking existing configurations
   - *Mitigation*: Implement migration system, maintain schema versioning

### Medium Risk Items
1. **Credential Migration**: Risk of losing access to external services
   - *Mitigation*: Clear migration guide, backup procedures

2. **Test Coverage**: Risk of tests not catching real issues
   - *Mitigation*: Include both unit and integration tests, hardware testing

## Recommended Starting Point

### Week 1-2 Immediate Actions (🔴 P0)

1. **Day 1-2**: Fix command injection vulnerability
   - Replace `os.system()` call in `base_plugin.py`
   - Test with malicious input to verify fix

2. **Day 3-5**: Implement secure credential storage
   - Create secure config loader
   - Migrate Spotify credentials to Keychain
   - Update plugin to use secure loader

3. **Day 6-10**: Add comprehensive input validation
   - Validate all plugin parameters
   - Add path traversal protection
   - Implement filename sanitization

4. **Day 11-14**: Basic error handling improvements
   - Add logging framework
   - Replace silent failures with proper error reporting
   - Implement basic recovery mechanisms

### Quick Wins for Immediate Impact
- [ ] Add connection health monitoring (LED status indicator)
- [ ] Implement configuration backup on startup
- [ ] Add verbose logging option for troubleshooting
- [ ] Create basic validation for key_def.json structure

This phased approach ensures that critical security vulnerabilities are addressed immediately while building a foundation for long-term improvements. The plan balances risk mitigation with feature enhancement, providing a clear roadmap for transforming the StreamDeck project into a robust, secure, and maintainable system.