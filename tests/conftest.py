"""
Shared pytest configuration and fixtures for StreamDeck tests
"""
import pytest
import json
import tempfile
import os
from unittest.mock import Mock, MagicMock
from pathlib import Path


@pytest.fixture
def sample_config_v1():
    """Legacy configuration format for backward compatibility testing"""
    return {
        "settings": {
            "rotate": "CCW"
        },
        "applications": {
            "_default": {
                "15": {
                    "key_sequence": "GUI+Q",
                    "color": "#FF0000",
                    "description": "Close App"
                }
            },
            "zoom.us": {
                "0": {
                    "key_sequence": "GUI+SHIFT+A",
                    "color": "#FFFF00",
                    "description": "Mute/Unmute"
                },
                "1": {
                    "key_sequence": "GUI+SHIFT+V",
                    "color": "#FFFF00",
                    "description": "Start/Stop Video"
                }
            }
        },
        "folders": {
            "test_folder": {
                "0": {
                    "action": "close_folder",
                    "color": "#FFFFFF",
                    "description": "Close"
                }
            }
        }
    }


@pytest.fixture
def sample_config_v2():
    """V2.0 configuration format with metadata and color scheme"""
    return {
        "metadata": {
            "version": "2.0.0",
            "description": "Test configuration",
            "created": "2024-01-01"
        },
        "color_scheme": {
            "navigation": "#FFFFFF",
            "creation": "#00FF00",
            "destruction": "#FF0000",
            "communication": "#FFFF00"
        },
        "settings": {
            "rotate": "CCW"
        },
        "applications": {
            "_default": {
                "15": {
                    "key_sequence": "GUI+Q",
                    "color": "#FF0000",
                    "description": "Quit: Application"
                }
            },
            "zoom.us": {
                "0": {
                    "key_sequence": "GUI+SHIFT+A",
                    "color": "#FFFF00",
                    "description": "Toggle: Audio Mute"
                }
            }
        },
        "folders": {}
    }


@pytest.fixture
def temp_config_file(sample_config_v1):
    """Create temporary configuration file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_config_v1, f)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    os.unlink(temp_file)


@pytest.fixture
def mock_serial():
    """Mock serial connection for testing"""
    mock = Mock()
    mock.in_waiting = 0
    mock.readline.return_value = b""
    mock.write = Mock()
    mock.close = Mock()
    return mock


@pytest.fixture
def mock_keypad():
    """Mock RGB keypad for Pi Pico testing"""
    mock = Mock()
    mock.keys = []
    
    # Create 16 mock keys (0-15)
    for i in range(16):
        key_mock = Mock()
        key_mock.number = i
        key_mock.led_off = Mock()
        key_mock.set_led = Mock()
        mock.keys.append(key_mock)
    
    mock.on_press = Mock()
    mock.on_release = Mock()
    mock.update = Mock()
    
    return mock


@pytest.fixture
def mock_keyboard():
    """Mock HID keyboard for testing"""
    mock = Mock()
    mock.press = Mock()
    mock.release_all = Mock()
    return mock


@pytest.fixture
def mock_spotify_client():
    """Mock Spotify client for plugin testing"""
    mock = Mock()
    
    # Mock user info
    mock.current_user.return_value = {"id": "test_user"}
    
    # Mock playback state
    mock.current_playback.return_value = {
        "is_playing": True,
        "device": {"volume_percent": 50}
    }
    
    # Mock track info
    mock.current_user_playing_track.return_value = {
        "is_playing": True,
        "item": {
            "name": "Test Song",
            "artists": [{"name": "Test Artist"}]
        }
    }
    
    # Mock control methods
    mock.start_playback = Mock()
    mock.pause_playback = Mock()
    mock.next_track = Mock()
    mock.previous_track = Mock()
    mock.volume = Mock()
    
    return mock


@pytest.fixture
def mock_hue_bridge():
    """Mock Hue bridge for plugin testing"""
    mock = Mock()
    
    # Mock lights
    light1 = Mock()
    light1.name = "Test Light 1"
    light1.on = True
    
    light2 = Mock()
    light2.name = "Test Light 2" 
    light2.on = False
    
    mock.lights = [light1, light2]
    mock.connect = Mock()
    
    return mock


@pytest.fixture
def invalid_config_files():
    """Create various invalid configuration files for error testing"""
    configs = {}
    
    # Malformed JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"invalid": "json"')  # Missing closing brace
        configs['malformed_json'] = f.name
    
    # Missing required sections
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"settings": {}}, f)  # Missing applications
        configs['missing_applications'] = f.name
    
    # Invalid colors
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        invalid_config = {
            "settings": {},
            "applications": {
                "test": {
                    "0": {
                        "key_sequence": "CTRL+A",
                        "color": "red",  # Invalid color format
                        "description": "Test"
                    }
                }
            },
            "folders": {}
        }
        json.dump(invalid_config, f)
        configs['invalid_colors'] = f.name
    
    yield configs
    
    # Cleanup
    for path in configs.values():
        os.unlink(path)


@pytest.fixture
def test_sound_file():
    """Create a temporary test sound file"""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        # Write minimal MP3 header (not a real MP3, just for testing)
        f.write(b'ID3\x04\x00\x00\x00\x00\x00\x00')
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    os.unlink(temp_file)


@pytest.fixture
def mock_application_monitor():
    """Mock macOS application monitoring for watchdog testing"""
    mock = Mock()
    mock.start_monitoring = Mock()
    mock.stop_monitoring = Mock()
    mock.get_active_application = Mock(return_value="Test App")
    return mock


# Pytest markers for test categorization
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "hardware: marks tests as requiring physical hardware"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security focused"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on location"""
    for item in items:
        # Mark hardware tests
        if "hardware" in str(item.fspath):
            item.add_marker(pytest.mark.hardware)
        
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            
        # Mark security tests
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)


# Skip hardware tests by default unless explicitly requested
def pytest_runtest_setup(item):
    """Setup function to handle test skipping"""
    if "hardware" in item.keywords:
        if not item.config.getoption("--run-hardware"):
            pytest.skip("Hardware tests skipped (use --run-hardware to enable)")


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--run-hardware",
        action="store_true", 
        default=False,
        help="Run hardware tests that require physical devices"
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests that take significant time"
    )