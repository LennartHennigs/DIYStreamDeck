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

    def test_named_colors(self):
        """Named colors resolve to full-brightness RGB tuples (matching key_def usage)"""
        assert self.controller.color_string_to_tuple("red") == (255, 0, 0)
        assert self.controller.color_string_to_tuple("green") == (0, 255, 0)
        assert self.controller.color_string_to_tuple("yellow") == (255, 255, 0)
        assert self.controller.color_string_to_tuple("blue") == (0, 0, 255)
        assert self.controller.color_string_to_tuple("black") == (0, 0, 0)
        assert self.controller.color_string_to_tuple("white") == (255, 255, 255)
        assert self.controller.color_string_to_tuple("orange") == (255, 165, 0)
        # case- and whitespace-insensitive
        assert self.controller.color_string_to_tuple("  RED ") == (255, 0, 0)
        assert self.controller.color_string_to_tuple("Green") == (0, 255, 0)
        # gray/grey aliases
        assert self.controller.color_string_to_tuple("gray") == (128, 128, 128)
        assert self.controller.color_string_to_tuple("grey") == (128, 128, 128)
        # unknown name still returns None (backward compatible)
        assert self.controller.color_string_to_tuple("chartreuse") is None
        # hex still works alongside names
        assert self.controller.color_string_to_tuple("#FFA500") == (255, 165, 0)

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

    def test_keypad_update_called_when_serial_data_present(self):
        """keypad.update() must be called even when serial data is being processed.

        Before the fix: keypad.update() only ran in the else branch (idle serial).
        During a burst of serial messages key presses were silently dropped.
        After the fix: keypad.update() runs unconditionally every iteration.
        """
        update_calls = []

        def _fake_update():
            update_calls.append(1)

        # Return serial data on the ONLY iteration, then stop — never enter the else branch.
        serial_iter = iter(["HB"])

        def _fake_read():
            try:
                val = next(serial_iter)
                return val
            except StopIteration:
                raise KeyboardInterrupt  # stop loop after the one serial-data iteration

        self.controller.keypad.update = _fake_update

        with patch.object(self.controller, 'read_serial_line', side_effect=_fake_read):
            try:
                self.controller.run()
            except KeyboardInterrupt:
                pass

        assert len(update_calls) >= 1, (
            "keypad.update() must be called even when serial data was received in that iteration; "
            "currently it is only called in the else (idle) branch, so key presses are dropped "
            "during serial bursts"
        )


class TestKeycodeMappingSharing:
    """KEYCODE_MAPPING must be built once and shared across instances."""

    @patch('builtins.open', mock_open(read_data=MOCK_JSON_CONFIG))
    def test_second_instance_reuses_mapping(self):
        """Instantiating KeyController twice must reuse the same KEYCODE_MAPPING object."""
        from src.pi_pico.code import KeyController
        kc1 = KeyController(verbose=False)
        kc2 = KeyController(verbose=False)
        assert KeyController.KEYCODE_MAPPING is not None
        assert kc1.KEYCODE_MAPPING is kc2.KEYCODE_MAPPING, (
            "KEYCODE_MAPPING should be the same object (class-level), not rebuilt per instance"
        )

# Config with nested folders for rotation / folder-stack hygiene tests
MOCK_FOLDER_STACK_CONFIG = '''{
    "settings": {"rotate": ""},
    "applications": {
        "_otherwise": {
            "0": {"key_sequence": "CMD+C", "color": "#00FF00", "description": "Copy"},
            "3": {"folder": "outer", "color": "#FFFFFF", "description": "Open outer"}
        },
        "AppX": {
            "1": {"key_sequence": "CMD+X", "color": "#FF0000", "description": "Cut"}
        }
    },
    "folders": {
        "outer": {
            "autoclose": "false",
            "0": {"folder": "inner", "color": "#FFFFFF", "description": "Open inner"},
            "1": {"key_sequence": "CMD+A", "color": "#FF00FF", "description": "Action in outer"},
            "2": {"action": "close_folder", "color": "#808080", "description": "Back"}
        },
        "inner": {
            "0": {"key_sequence": "SPACE", "color": "#FF8000", "description": "Action in inner"}
        }
    }
}'''


class TestRotationSetsNotComposes:
    """Bug fix: 'Rotate:' commands composed with the current (already rotated)
    layout instead of setting an absolute rotation of the pristine config."""

    @patch('builtins.open', mock_open(read_data=MOCK_JSON_CONFIG))
    def setup_method(self, method):
        from src.pi_pico.code import KeyController
        self.controller = KeyController(verbose=True)

    def test_rotate_cw_twice_equals_once(self):
        self.controller.process_serial_str("Rotate: CW")
        once = dict(self.controller.current_config)
        self.controller.process_serial_str("Rotate: CW")
        assert self.controller.current_config == once

    def test_rotate_cw_then_ccw_gives_ccw_layout(self):
        baseline = dict(self.controller.current_config)  # unrotated, keys {0, 1}
        self.controller.process_serial_str("Rotate: CW")
        self.controller.process_serial_str("Rotate: CCW")
        # CCW places source key 0 at position 12 and source key 1 at position 8
        expected = {12: baseline[0], 8: baseline[1]}
        assert self.controller.current_config == expected


class TestFolderStackHygiene:
    """Bug fix: folder stack leaked across app switches, and closing a nested
    folder lost the parent folder's autoclose flag."""

    @patch('builtins.open', mock_open(read_data=MOCK_FOLDER_STACK_CONFIG))
    def setup_method(self, method):
        from src.pi_pico.code import KeyController
        self.controller = KeyController(verbose=True)

    def test_app_switch_clears_folder_stack(self):
        self.controller.key_press_action(self.controller.keypad.keys[3])  # open outer
        assert len(self.controller.folder_stack) == 1
        self.controller.process_serial_str("App: AppX")
        assert self.controller.folder_stack == []

    def test_nested_folder_close_restores_parent_autoclose(self):
        keys = self.controller.keypad.keys
        self.controller.key_press_action(keys[3])  # open outer (autoclose false)
        self.controller.key_press_action(keys[0])  # open inner (autoclose true)
        self.controller.key_press_action(keys[0])  # action in inner -> autocloses to outer
        assert len(self.controller.folder_stack) == 1
        assert 2 in self.controller.current_config  # back in outer (has close_folder key)
        # outer has autoclose false: an action must NOT close it
        self.controller.key_press_action(keys[1])
        assert len(self.controller.folder_stack) == 1
        assert 2 in self.controller.current_config
