"""
Real security tests that test actual codebase for vulnerabilities
"""
import pytest
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock the playsound module before importing
sys.modules['playsound'] = MagicMock()

try:
    from src.mac.plugins.sounds import SoundsPlugin
except ImportError as e:
    pytest.skip(f"SoundsPlugin not available: {e}", allow_module_level=True)


class TestActualVulnerabilities:
    """Test actual security vulnerabilities in the StreamDeck codebase"""
    
    def setup_method(self):
        """Set up test environment"""
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "sounds_config.json")
        
        config = {
            "sound_path": "sounds/"
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f)
    
    def test_sounds_plugin_path_traversal_vulnerability(self):
        """Test that SoundsPlugin properly prevents path traversal attacks"""
        
        with patch('src.mac.plugins.sounds.playsound') as mock_playsound:
            plugin = SoundsPlugin(self.config_file, verbose=False)
            
            # Test various path traversal attempts - all should be blocked
            malicious_filenames = [
                "../../../etc/passwd",           # Classic path traversal
                "..\\..\\..\\windows\\system32", # Windows path traversal  
                "/etc/shadow",                   # Absolute path
                "../../sensitive.txt",          # Relative traversal
                "sounds/../../../etc/passwd",   # Embedded traversal
                "file\x00.mp3",                 # Null byte injection
            ]
            
            for malicious_filename in malicious_filenames:
                with pytest.raises(Exception, match="Invalid filename|Invalid file path"):
                    # All malicious filenames should be rejected with security validation
                    plugin.play(malicious_filename)
            
            # Test that normal filenames are processed (even if file doesn't exist)
            normal_filenames = [
                "song.mp3",
                "notification.wav", 
                "alert.mp3"
            ]
            
            for normal_filename in normal_filenames:
                with pytest.raises(Exception, match="not found"):
                    # Normal filenames should be processed but fail because file doesn't exist
                    plugin.play(normal_filename)

    def test_sounds_plugin_filename_validation(self):
        """Test if SoundsPlugin validates filenames properly"""
        with patch('src.mac.plugins.sounds.playsound') as mock_playsound:
            plugin = SoundsPlugin(self.config_file, verbose=False)
            
            # Test various malicious filenames
            invalid_filenames = [
                "",                             # Empty filename
                " ",                           # Whitespace only
                "file\x00name.mp3",           # Null byte injection
                "file\nname.mp3",             # Newline injection
                "file;rm -rf /.mp3",          # Command injection attempt
                "file`rm -rf /`.mp3",         # Backtick injection
                "$(rm -rf /).mp3",            # Command substitution
            ]
            
            for invalid_filename in invalid_filenames:
                with pytest.raises(Exception):
                    # Should raise exception for invalid filenames
                    plugin.play(invalid_filename)

    def test_sounds_plugin_config_injection(self):
        """Test if config loading is vulnerable to injection"""
        # Create malicious config file
        malicious_config_file = os.path.join(self.temp_dir, "malicious_config.json")
        
        # This config tries to escape the sound directory
        malicious_config = {
            "sound_path": "../../../"
        }
        
        with open(malicious_config_file, 'w') as f:
            json.dump(malicious_config, f)
        
        with patch('src.mac.plugins.sounds.playsound') as mock_playsound:
            plugin = SoundsPlugin(malicious_config_file, verbose=False)
            
            # Even with malicious config, path traversal should be prevented
            with pytest.raises(Exception):
                plugin.play("etc/passwd")

    def teardown_method(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestInputValidationActual:
    """Test input validation in actual codebase components"""
    
    def test_json_config_parsing_safety(self):
        """Test that JSON config parsing is safe"""
        # Create config with potentially dangerous content
        temp_dir = tempfile.mkdtemp()
        config_file = os.path.join(temp_dir, "test_config.json")
        
        try:
            # Test that JSON parsing doesn't execute code
            dangerous_json_content = '''
            {
                "sound_path": "sounds/",
                "__import__": "os",
                "eval": "os.system('echo vulnerable')"
            }
            '''
            
            with open(config_file, 'w') as f:
                f.write(dangerous_json_content)
            
            with patch('src.mac.plugins.sounds.playsound'):
                plugin = SoundsPlugin(config_file, verbose=False)
                
                # Ensure dangerous keys are not executed
                assert plugin.config.get("__import__") == "os"  # Should be string, not executed
                assert plugin.config.get("eval") == "os.system('echo vulnerable')"  # Should be string, not executed
                
                # The plugin should work normally despite dangerous keys
                assert plugin.sound_path == "sounds/"
        
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)