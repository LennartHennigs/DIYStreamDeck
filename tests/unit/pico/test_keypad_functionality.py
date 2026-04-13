import sys
import os
import pytest
import time
from unittest.mock import patch, mock_open, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

# Import mock CircuitPython modules BEFORE importing code.py
from tests.unit.pico.mock_circuitpython import MockUSBCDC, MockRgbKeypad

# Enhanced mock JSON config with folders and more complex key definitions
MOCK_KEYPAD_CONFIG = '''{
    "settings": {
        "rotate": ""
    },
    "applications": {
        "_default": {
            "0": {
                "key_sequence": "CMD+A",
                "color": "#FF0000",
                "description": "Select All"
            },
            "1": {
                "key_sequence": "CMD+C",
                "color": "#00FF00",
                "description": "Copy"
            }
        },
        "_otherwise": {
            "2": {
                "key_sequence": "CMD+V",
                "color": "#0000FF",
                "description": "Paste"
            },
            "3": {
                "folder": "media_controls",
                "color": "#FFFF00",
                "description": "Media Controls"
            }
        },
        "TestApp": {
            "0": {
                "key_sequence": ["CMD+S", 0.1, "ENTER"],
                "color": "#FF00FF",
                "description": "Save and Enter",
                "pressedUntilReleased": true
            },
            "1": {
                "key_sequence": "CMD+Z",
                "color": "#00FFFF",
                "toggleColor": "#FFFF00",
                "description": "Undo with toggle"
            },
            "2": {
                "action": "spotify.play",
                "color": "#800080",
                "description": "Spotify Play"
            }
        }
    },
    "folders": {
        "media_controls": {
            "0": {
                "key_sequence": "SPACE",
                "color": "#FF8000",
                "description": "Play/Pause"
            },
            "1": {
                "action": "close_folder",
                "color": "#808080",
                "description": "Back"
            },
            "autoclose": "false"
        }
    },
    "urls": {
        "example.com": {
            "0": {
                "key_sequence": "CMD+R",
                "color": "#804000",
                "description": "Refresh page"
            }
        }
    }
}'''


class TestKeypadFunctionality:
    @patch('builtins.open', mock_open(read_data=MOCK_KEYPAD_CONFIG))
    def setup_method(self, method):
        """Setup for each test method"""
        from src.pi_pico.code import KeyController
        self.controller = KeyController(verbose=True)
        
    def test_key_led_initialization(self):
        """Test that LEDs are properly initialized with colors"""
        # Check that default keys have correct colors
        key_0 = self.controller.keypad.keys[0]
        key_1 = self.controller.keypad.keys[1]
        
        # Key 0 should have red color from _default config
        assert key_0.led_color == (255, 0, 0)  # #FF0000
        # Key 1 should have green color from _default config
        assert key_1.led_color == (0, 255, 0)  # #00FF00
        
    def test_key_press_handling(self):
        """Test basic key press functionality"""
        # Simulate key press on configured key
        key_0 = self.controller.keypad.keys[0]
        
        # Press the key
        self.controller.key_press_action(key_0)
        
        # Keys are immediately released unless pressedUntilReleased is true
        # So let's check that the action was processed (no exception = success)
        assert True  # Key press completed without error
        
    def test_key_release_handling(self):
        """Test key release functionality"""
        key_0 = self.controller.keypad.keys[0]
        
        # Press then release
        self.controller.key_press_action(key_0)
        self.controller.key_release_action(key_0)
        
        # Keys should be released
        assert len(self.controller.keyboard.pressed_keys) == 0
        
    def test_key_sequences_with_delays(self):
        """Test complex key sequences including delays"""
        # Switch to TestApp which has complex sequences
        self.controller.process_serial_str("App: TestApp")
        
        key_0 = self.controller.keypad.keys[0]
        
        # This key has sequence: ["CMD+S", 0.1, "ENTER"]
        with patch('time.sleep') as mock_sleep:
            self.controller.key_press_action(key_0)
            # Should have called sleep for the delay
            mock_sleep.assert_called_with(0.1)
            
    def test_pressed_until_released_keys(self):
        """Test keys that stay pressed until released"""
        # Switch to TestApp
        self.controller.process_serial_str("App: TestApp")
        
        key_0 = self.controller.keypad.keys[0]
        
        # Press key (should stay pressed due to pressedUntilReleased: true)
        self.controller.key_press_action(key_0)
        
        # Keys should still be pressed
        assert len(self.controller.keyboard.pressed_keys) > 0
        
        # Release should clear them
        self.controller.key_release_action(key_0)
        assert len(self.controller.keyboard.pressed_keys) == 0
        
    def test_toggle_color_functionality(self):
        """Test color toggling on key press/release"""
        # Switch to TestApp
        self.controller.process_serial_str("App: TestApp")
        
        key_1 = self.controller.keypad.keys[1]
        original_color = key_1.led_color
        
        # Press and release to trigger toggle
        self.controller.key_press_action(key_1)
        self.controller.key_release_action(key_1)
        
        # Color should have changed
        assert key_1.led_color != original_color
        
    def test_folder_navigation(self):
        """Test opening and navigating folders"""
        # Press key 3 which opens media_controls folder
        key_3 = self.controller.keypad.keys[3]
        self.controller.key_press_action(key_3)
        
        # Should be in folder now
        assert len(self.controller.folder_stack) == 1
        
        # Key 0 should now have the folder's configuration
        key_0 = self.controller.keypad.keys[0]
        assert key_0.led_color == (255, 128, 0)  # #FF8000 from folder config
        
    def test_folder_autoclose_behavior(self):
        """Test folder autoclose functionality"""
        # Open media_controls folder (autoclose: false)
        key_3 = self.controller.keypad.keys[3]
        self.controller.key_press_action(key_3)
        
        # Press key 0 in folder (should NOT autoclose)
        key_0 = self.controller.keypad.keys[0]
        self.controller.key_press_action(key_0)
        
        # Should still be in folder
        assert len(self.controller.folder_stack) == 1
        
        # Press key 1 (close_folder action)
        key_1 = self.controller.keypad.keys[1]
        self.controller.key_press_action(key_1)
        
        # Should have closed folder
        assert len(self.controller.folder_stack) == 0
        
    def test_plugin_command_execution(self):
        """Test plugin command execution"""
        console = sys.modules['usb_cdc'].console
        
        # Clear any existing output
        if hasattr(console, 'get_output'):
            console.get_output()
        
        # Switch to TestApp
        self.controller.process_serial_str("App: TestApp")
        
        # Press key 2 which has action: "spotify.play"
        key_2 = self.controller.keypad.keys[2]
        self.controller.key_press_action(key_2)
        
        # Should have sent plugin command
        output = console.get_output() if hasattr(console, 'get_output') else ""
        assert "Run: spotify.play" in output
        
    def test_application_launch_command(self):
        """Test application launch commands"""
        console = sys.modules['usb_cdc'].console
        
        # Create config with application launch
        config = {
            "4": {
                "application": "Calculator",
                "color": "#FFFFFF"
            }
        }
        
        # Manually add to current config
        self.controller.current_config[4] = {
            'application': 'Calculator',
            'color': (255, 255, 255),
            'key_sequences': (),
            'action': '',
            'folder': '',
            'toggleColor': False,
            'pressedColor': False,
            'description': '',
            'pressedUntilReleased': ''
        }
        self.controller.update_keys()
        
        # Clear any existing output
        if hasattr(console, 'get_output'):
            console.get_output()
        
        # Press key 4
        key_4 = self.controller.keypad.keys[4]
        self.controller.key_press_action(key_4)
        
        # Should have sent launch command
        output = console.get_output() if hasattr(console, 'get_output') else ""
        assert "Launch: Calculator" in output
        
    def test_url_specific_configuration(self):
        """Test URL-specific key configurations"""
        # Load URL config
        self.controller.process_serial_str("App: Chrome (example.com)")
        
        # Should have loaded URL-specific config
        key_0 = self.controller.keypad.keys[0]
        assert key_0.led_color == (128, 64, 0)  # #804000
        
    def test_undefined_key_handling(self):
        """Test behavior with undefined keys"""
        # Key 15 is not defined in config
        key_15 = self.controller.keypad.keys[15]
        
        # Should be off
        assert key_15.led_color == (0, 0, 0)
        
        # Pressing should do nothing (no exception)
        self.controller.key_press_action(key_15)
        assert True  # If we reach here, no exception was thrown
        
    def test_key_rotation_cw(self):
        """Test clockwise key rotation"""
        # Apply rotation
        self.controller.process_serial_str("Rotate: CW")
        
        # Check that rotation was applied
        assert self.controller.rotate == "CW"
        
    def test_key_rotation_ccw(self):
        """Test counter-clockwise key rotation"""
        # Apply rotation
        self.controller.process_serial_str("Rotate: CCW")
        
        # Check that rotation was applied
        assert self.controller.rotate == "CCW"
        
    def test_keypad_clearing(self):
        """Test keypad clearing functionality"""
        # Initially some keys should be lit
        assert any(key.led_color != (0, 0, 0) for key in self.controller.keypad.keys)
        
        # Clear keypad
        self.controller.clear_keypad()
        
        # All keys should be off
        assert all(key.led_color == (0, 0, 0) for key in self.controller.keypad.keys)
        assert self.controller.current_config == {}
        
    def test_keypad_reload_after_clear(self):
        """Test keypad reload after clearing"""
        # Clear keypad
        self.controller.clear_keypad()
        assert all(key.led_color == (0, 0, 0) for key in self.controller.keypad.keys)
        
        # Reload basic config
        self.controller.load_basic_config()
        
        # Keys should be lit again
        assert any(key.led_color != (0, 0, 0) for key in self.controller.keypad.keys)
        assert len(self.controller.current_config) > 0
        
    def test_invalid_keycode_handling(self):
        """Test handling of invalid keycodes"""
        with pytest.raises(ValueError, match="Unknown keycode constant"):
            self.controller.keycode_string_to_tuple("INVALID_KEY")
            
    def test_invalid_color_handling(self):
        """Test handling of invalid color formats"""
        # Valid hex color
        assert self.controller.color_string_to_tuple("#FF0000") == (255, 0, 0)
        
        # Invalid color format — must return None, not False
        assert self.controller.color_string_to_tuple("red") is None
        assert self.controller.color_string_to_tuple("invalid") is None
        
    def test_key_update_after_app_change(self):
        """Test key updates when switching applications"""
        # Start with _otherwise config
        original_key_2_color = self.controller.keypad.keys[2].led_color
        
        # Switch to TestApp
        self.controller.process_serial_str("App: TestApp")
        
        # Key 2 should have different color now
        new_key_2_color = self.controller.keypad.keys[2].led_color
        assert new_key_2_color != original_key_2_color
        assert new_key_2_color == (128, 0, 128)  # #800080
        
    def test_termination_handling(self):
        """Test application termination handling"""
        # Switch to TestApp with toggle color
        self.controller.process_serial_str("App: TestApp")
        
        # Simulate app termination (should reload config)
        self.controller.process_serial_str("Terminated: TestApp")
        
        # Config should be reloaded (no exception means success)
        assert self.controller.apps.get("TestApp") is not None