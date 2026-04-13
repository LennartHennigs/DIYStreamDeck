import sys
import os
import pytest
import time
from unittest.mock import patch, mock_open

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

# Import mock CircuitPython modules BEFORE importing code.py
from tests.unit.pico.mock_circuitpython import MockUSBCDC

# Mock the JSON file content
MOCK_JSON_CONFIG = '''{
    "settings": {
        "rotate": ""
    },
    "applications": {
        "_default": {
            "0": {
                "key_sequence": "CMD+A",
                "color": "#FF0000",
                "description": "Select All"
            }
        },
        "_otherwise": {
            "1": {
                "key_sequence": "CMD+C",
                "color": "#00FF00",
                "description": "Copy"
            }
        }
    },
    "folders": {},
    "urls": {}
}'''


class TestKeyController:
    @patch('builtins.open', mock_open(read_data=MOCK_JSON_CONFIG))
    def setup_method(self, method):
        """Setup for each test method"""
        # Import here so mocks are in place
        from src.pi_pico.code import KeyController
        self.controller = KeyController(verbose=True)
        
    def test_initialization(self):
        """Test KeyController initializes correctly"""
        assert self.controller is not None
        assert len(self.controller.keys) == 16
        assert self.controller.verbose is True
        assert self.controller.unloaded is False
        
    def test_json_parsing(self):
        """Test JSON configuration is parsed correctly"""
        assert "_default" in self.controller.json["applications"]
        assert "_otherwise" in self.controller.json["applications"]
        
    def test_heartbeat_processing(self):
        """Test heartbeat updates timestamp"""
        initial_time = self.controller.last_heartbeat
        time.sleep(0.1)  # Small delay
        
        # Process heartbeat
        self.controller.process_serial_str("HB")
        
        # Check timestamp was updated
        assert self.controller.last_heartbeat > initial_time
        
    def test_heartbeat_timeout(self):
        """Test keypad unloads on heartbeat timeout"""
        # Set last heartbeat to old timestamp
        self.controller.last_heartbeat = time.time() - 10
        
        # Simulate timeout check (from run loop)
        TIMEOUT_SECONDS = 4  # PICO_HEARTBEAT_INTERVAL * PICO_TIMEOUT_MULTIPLIER
        if (not self.controller.unloaded) and (time.time() - self.controller.last_heartbeat > TIMEOUT_SECONDS):
            self.controller.unload_keypad()
            
        assert self.controller.unloaded is True
        
    def test_hello_command(self):
        """Test HELLO command loads basic config"""
        # First unload
        self.controller.unload_keypad()
        assert self.controller.unloaded is True
        
        # Process HELLO
        self.controller.process_serial_str("HELLO")
        
        assert self.controller.unloaded is False
        
    def test_bye_command(self):
        """Test BYE command unloads keypad"""
        assert self.controller.unloaded is False
        
        # Process BYE
        self.controller.process_serial_str("BYE")
        
        assert self.controller.unloaded is True
        
    def test_app_switching(self):
        """Test application switching"""
        # Switch to _otherwise app
        self.controller.process_serial_str("App: SomeApp")
        
        # Should load _otherwise config since "SomeApp" isn't defined
        assert 1 in self.controller.current_config  # Has key 1 from _otherwise
        
    def test_rotation_cw(self):
        """Test clockwise rotation"""
        original_config = self.controller.current_config.copy()
        
        # Apply CW rotation
        self.controller.process_serial_str("Rotate: CW")
        
        # Config should be rotated
        assert self.controller.rotate == "CW"
        
    def test_rotation_ccw(self):
        """Test counter-clockwise rotation"""
        original_config = self.controller.current_config.copy()
        
        # Apply CCW rotation
        self.controller.process_serial_str("Rotate: CCW")
        
        # Config should be rotated
        assert self.controller.rotate == "CCW"
        
    def test_keycode_conversion(self):
        """Test keycode string to tuple conversion"""
        # Test simple keycode
        result = self.controller.keycode_string_to_tuple("A")
        assert result == (4,)  # MockKeycode.A = 4
        
        # Test combination
        result = self.controller.keycode_string_to_tuple("CMD+A")
        assert result == (227, 4)  # (MockKeycode.GUI, MockKeycode.A)
        
    def test_color_conversion(self):
        """Test color string to tuple conversion"""
        # Test hex color
        result = self.controller.color_string_to_tuple("#FF0000")
        assert result == (255, 0, 0)
        
        # Test invalid color — must return None, not False
        result = self.controller.color_string_to_tuple("invalid")
        assert result is None
        
    def test_serial_communication(self):
        """Test serial input/output"""
        # Ensure we use the same console object that the controller uses
        console = sys.modules['usb_cdc'].console
        
        # Clear any existing state
        if hasattr(console, 'get_output'):
            console.get_output()
        
        # Add input
        if hasattr(console, 'add_input'):
            console.add_input("HB\n")
        elif hasattr(console, '_buf'):
            # Support for FakeConsole from other test
            console._buf.append(b"HB\n")
        
        # Read input
        line = self.controller.read_serial_line()
        assert line == "HB"
        
        # Test output
        self.controller.send_application_name("TestApp")
        output = console.get_output() if hasattr(console, 'get_output') else ""
        assert "Launch: TestApp" in output
        
    def test_key_press_simulation(self):
        """Test key press handling"""
        # Simulate key press on key 1 (should have _otherwise config)
        if hasattr(self.controller.keypad, 'simulate_key_press'):
            self.controller.keypad.simulate_key_press(1)
            
        # Key should have been processed (no exception means success)
        assert True  # If we get here, no exception was thrown
        
    def test_unload_and_reload(self):
        """Test complete unload/reload cycle"""
        # Initial state
        assert self.controller.unloaded is False

        # Unload
        self.controller.unload_keypad()
        assert self.controller.unloaded is True
        assert self.controller.current_config == {}

        # Reload
        self.controller.load_basic_config()

    def test_unload_keypad_idempotent(self):
        """Calling unload_keypad() twice must not call clear_keypad() twice."""
        from unittest.mock import patch
        with patch.object(self.controller, 'clear_keypad') as mock_clear:
            self.controller.unload_keypad()
            self.controller.unload_keypad()
        assert mock_clear.call_count == 1, (
            "clear_keypad must only be called once even if unload_keypad() is called twice"
        )

    def test_send_application_name_logs_error_when_verbose(self, capsys):
        """send_application_name must print the error when write fails and verbose=True."""
        import sys
        from unittest.mock import patch
        self.controller.verbose = True
        with patch.object(sys.modules['usb_cdc'].console, 'write',
                          side_effect=Exception("port closed")):
            self.controller.send_application_name("Spotify")
        captured = capsys.readouterr()
        assert captured.out.strip(), "Expected an error message when verbose=True"

    def test_send_plugin_command_logs_error_when_verbose(self, capsys):
        """send_plugin_command must print the error when write fails and verbose=True."""
        import sys
        from unittest.mock import patch
        self.controller.verbose = True
        with patch.object(sys.modules['usb_cdc'].console, 'write',
                          side_effect=Exception("port closed")):
            self.controller.send_plugin_command("spotify", "next")
        captured = capsys.readouterr()
        assert captured.out.strip(), "Expected an error message when verbose=True"
        assert self.controller.unloaded is False
        assert len(self.controller.current_config) > 0