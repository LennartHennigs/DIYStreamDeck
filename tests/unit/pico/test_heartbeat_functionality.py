import sys
import os
import pytest
import time
from unittest.mock import patch, mock_open, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

# Import mock CircuitPython modules BEFORE importing code.py
from tests.unit.pico.mock_circuitpython import MockUSBCDC

# Minimal JSON config for heartbeat testing
HEARTBEAT_TEST_CONFIG = '''{
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


class TestHeartbeatFunctionality:
    @patch('builtins.open', mock_open(read_data=HEARTBEAT_TEST_CONFIG))
    def setup_method(self, method):
        """Setup for each test method"""
        from src.pi_pico.code import KeyController
        self.controller = KeyController(verbose=True)
        
    def test_heartbeat_initialization(self):
        """Test heartbeat timestamp is set on initialization"""
        # Should have a recent timestamp
        assert self.controller.last_heartbeat > 0
        assert abs(time.time() - self.controller.last_heartbeat) < 1.0
        assert self.controller.unloaded is False
        
    def test_heartbeat_processing(self):
        """Test heartbeat command updates timestamp"""
        # Get initial timestamp
        initial_heartbeat = self.controller.last_heartbeat
        
        # Wait a tiny bit to ensure timestamp difference
        time.sleep(0.01)
        
        # Process heartbeat command
        self.controller.process_serial_str("HB")
        
        # Timestamp should be updated
        assert self.controller.last_heartbeat > initial_heartbeat
        assert self.controller.unloaded is False
        
    def test_multiple_heartbeats(self):
        """Test multiple heartbeat commands keep updating timestamp"""
        timestamps = []
        
        # Send multiple heartbeats with small delays
        for i in range(5):
            self.controller.process_serial_str("HB")
            timestamps.append(self.controller.last_heartbeat)
            time.sleep(0.01)
            
        # Each timestamp should be later than the previous
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1]
            
        assert self.controller.unloaded is False
        
    def test_heartbeat_timeout_detection(self):
        """Test keypad unloads when heartbeat times out"""
        # Set old timestamp to simulate timeout
        old_time = time.time() - 10  # 10 seconds ago
        self.controller.last_heartbeat = old_time
        
        # Simulate timeout check from run loop
        TIMEOUT_SECONDS = 4  # PICO_HEARTBEAT_INTERVAL * PICO_TIMEOUT_MULTIPLIER
        current_time = time.time()
        
        if (not self.controller.unloaded) and (current_time - self.controller.last_heartbeat > TIMEOUT_SECONDS):
            self.controller.unload_keypad()
            
        # Should be unloaded due to timeout
        assert self.controller.unloaded is True
        assert self.controller.current_config == {}
        
    def test_heartbeat_prevents_timeout(self):
        """Test regular heartbeats prevent timeout"""
        # Set timestamp just under timeout threshold
        TIMEOUT_SECONDS = 4
        self.controller.last_heartbeat = time.time() - (TIMEOUT_SECONDS - 1)
        
        # Check if timeout would occur
        if (not self.controller.unloaded) and (time.time() - self.controller.last_heartbeat > TIMEOUT_SECONDS):
            self.controller.unload_keypad()
            
        # Should NOT be unloaded (within timeout window)
        assert self.controller.unloaded is False
        
        # Send heartbeat to refresh
        self.controller.process_serial_str("HB")
        
        # Still should not be unloaded
        assert self.controller.unloaded is False
        
    def test_hello_command_resets_heartbeat(self):
        """Test HELLO command updates heartbeat timestamp"""
        initial_time = self.controller.last_heartbeat
        time.sleep(0.01)
        
        # Process HELLO command
        self.controller.process_serial_str("HELLO")
        
        # Should update timestamp and ensure not unloaded
        assert self.controller.last_heartbeat > initial_time
        assert self.controller.unloaded is False
        
    def test_heartbeat_recovery_after_timeout(self):
        """Test recovery from timeout state with HELLO"""
        # Force timeout state
        self.controller.last_heartbeat = time.time() - 10
        self.controller.unload_keypad()
        assert self.controller.unloaded is True
        
        # Send HELLO to recover
        self.controller.process_serial_str("HELLO")
        
        # Should be recovered
        assert self.controller.unloaded is False
        assert len(self.controller.current_config) > 0
        assert abs(time.time() - self.controller.last_heartbeat) < 1.0
        
    def test_bye_command_ignores_heartbeat_state(self):
        """Test BYE command unloads regardless of heartbeat"""
        # Ensure good heartbeat state
        self.controller.process_serial_str("HB")
        assert self.controller.unloaded is False
        
        # Send BYE command
        self.controller.process_serial_str("BYE")
        
        # Should be unloaded despite good heartbeat
        assert self.controller.unloaded is True
        
    def test_heartbeat_with_app_switching(self):
        """Test heartbeat works during app switching"""
        initial_time = self.controller.last_heartbeat
        
        # Switch app and send heartbeat
        self.controller.process_serial_str("App: TestApp")
        time.sleep(0.01)
        self.controller.process_serial_str("HB")
        
        # Heartbeat should still work
        assert self.controller.last_heartbeat > initial_time
        assert self.controller.unloaded is False
        
    def test_heartbeat_during_rotation(self):
        """Test heartbeat works during key rotation"""
        initial_time = self.controller.last_heartbeat
        
        # Apply rotation and send heartbeat
        self.controller.process_serial_str("Rotate: CW")
        time.sleep(0.01)
        self.controller.process_serial_str("HB")
        
        # Heartbeat should still work
        assert self.controller.last_heartbeat > initial_time
        assert self.controller.unloaded is False
        assert self.controller.rotate == "CW"
        
    def test_heartbeat_idempotent_unload(self):
        """Test multiple timeout checks don't cause issues"""
        # Force timeout state
        self.controller.last_heartbeat = time.time() - 10
        self.controller.unload_keypad()
        assert self.controller.unloaded is True
        
        # Multiple unload attempts should be safe
        self.controller.unload_keypad()
        self.controller.unload_keypad()
        
        # Should still be unloaded with no side effects
        assert self.controller.unloaded is True
        assert self.controller.current_config == {}
        
    def test_heartbeat_timeout_constants(self):
        """Test heartbeat timeout constants are correctly configured"""
        from src.pi_pico.code import PICO_HEARTBEAT_INTERVAL, PICO_TIMEOUT_MULTIPLIER
        
        # Verify timeout configuration
        assert PICO_HEARTBEAT_INTERVAL == 2  # 2 seconds
        assert PICO_TIMEOUT_MULTIPLIER == 2  # 2x multiplier
        
        # Total timeout should be 4 seconds
        total_timeout = PICO_HEARTBEAT_INTERVAL * PICO_TIMEOUT_MULTIPLIER
        assert total_timeout == 4
        
    def test_heartbeat_edge_case_exact_timeout(self):
        """Test behavior at exact timeout boundary"""
        TIMEOUT_SECONDS = 4
        
        # Set timestamp to exactly timeout threshold
        self.controller.last_heartbeat = time.time() - TIMEOUT_SECONDS
        
        # Small delay to ensure we're just over the threshold
        time.sleep(0.001)
        
        # Check timeout
        if (not self.controller.unloaded) and (time.time() - self.controller.last_heartbeat > TIMEOUT_SECONDS):
            self.controller.unload_keypad()
            
        # Should be unloaded
        assert self.controller.unloaded is True
        
    def test_heartbeat_preserves_config_state(self):
        """Test heartbeat doesn't affect current configuration"""
        # Get initial config state
        initial_config = self.controller.current_config.copy()
        
        # Send multiple heartbeats
        for _ in range(5):
            self.controller.process_serial_str("HB")
            time.sleep(0.01)
            
        # Config should be unchanged
        assert self.controller.current_config == initial_config
        assert self.controller.unloaded is False
        
    def test_heartbeat_with_serial_errors(self):
        """Test heartbeat handling with serial communication"""
        console = sys.modules['usb_cdc'].console
        
        # Clear any existing output
        console.get_output()
        
        # Process heartbeat (should not generate output)
        self.controller.process_serial_str("HB")
        
        # No output should be generated for heartbeat
        output = console.get_output()
        assert output == ""
        
    @patch('time.time')
    def test_heartbeat_timeout_simulation(self, mock_time):
        """Test timeout behavior with controlled time"""
        # Start at time 100
        mock_time.return_value = 100
        self.controller.last_heartbeat = 100
        
        # Advance time to just before timeout (103.9 seconds)
        mock_time.return_value = 103.9
        
        # Should not timeout yet
        if (not self.controller.unloaded) and (mock_time.return_value - self.controller.last_heartbeat > 4):
            self.controller.unload_keypad()
        assert self.controller.unloaded is False
        
        # Advance time past timeout (104.1 seconds)  
        mock_time.return_value = 104.1
        
        # Should timeout now
        if (not self.controller.unloaded) and (mock_time.return_value - self.controller.last_heartbeat > 4):
            self.controller.unload_keypad()
        assert self.controller.unloaded is True
        
    def test_heartbeat_after_keypad_clear(self):
        """Test heartbeat still works after keypad is cleared"""
        # Clear keypad manually
        self.controller.clear_keypad()
        initial_time = self.controller.last_heartbeat
        
        time.sleep(0.01)
        
        # Send heartbeat
        self.controller.process_serial_str("HB")
        
        # Heartbeat should still update timestamp
        assert self.controller.last_heartbeat > initial_time
        
    def test_heartbeat_in_folder_mode(self):
        """Test heartbeat works when in folder navigation"""
        # Add a folder to config for testing
        self.controller.folders = {
            "test_folder": {
                "autoclose": False,
                0: {
                    "key_sequences": (),
                    "color": (255, 0, 0),
                    "action": "",
                    "folder": "",
                    "application": "",
                    "toggleColor": False,
                    "pressedColor": False,
                    "description": "",
                    "pressedUntilReleased": ""
                }
            }
        }
        
        # Open folder
        self.controller.open_folder("test_folder")
        assert len(self.controller.folder_stack) == 1
        
        initial_time = self.controller.last_heartbeat
        time.sleep(0.01)
        
        # Send heartbeat while in folder
        self.controller.process_serial_str("HB")
        
        # Should still work
        assert self.controller.last_heartbeat > initial_time
        assert self.controller.unloaded is False
        assert len(self.controller.folder_stack) == 1  # Still in folder