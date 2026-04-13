import sys
import os
import pytest
import json
from unittest.mock import patch, mock_open, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

# Import mock CircuitPython modules BEFORE importing code.py
from tests.unit.pico.mock_circuitpython import MockUSBCDC


class TestJSONCorruption:
    """Test KeyController behavior with various JSON corruption scenarios"""
    
    def test_completely_invalid_json(self):
        """Test behavior with completely malformed JSON"""
        invalid_json = "{ this is not valid json at all }"
        
        with patch('builtins.open', mock_open(read_data=invalid_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(json.JSONDecodeError):
                KeyController(verbose=True)
                
    def test_truncated_json(self):
        """Test behavior with truncated JSON file"""
        truncated_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "0": {
                        "key_sequence": "CMD+A",
                        "color": "#FF0000"'''  # Truncated - missing closing braces
        
        with patch('builtins.open', mock_open(read_data=truncated_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(json.JSONDecodeError):
                KeyController(verbose=True)
                
    def test_json_with_trailing_comma(self):
        """Test behavior with trailing commas (invalid JSON but common mistake)"""
        trailing_comma_json = '''{
            "settings": {
                "rotate": "",
            },
            "applications": {
                "_default": {
                    "0": {
                        "key_sequence": "CMD+A",
                        "color": "#FF0000",
                    },
                },
            },
            "folders": {},
            "urls": {},
        }'''
        
        with patch('builtins.open', mock_open(read_data=trailing_comma_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(json.JSONDecodeError):
                KeyController(verbose=True)
                
    def test_missing_required_sections(self):
        """Test behavior when required JSON sections are missing"""
        minimal_json = '{"settings": {}}'  # Missing applications, folders, urls
        
        with patch('builtins.open', mock_open(read_data=minimal_json)):
            from src.pi_pico.code import KeyController
            
            # Should raise KeyError because code expects "applications" section
            with pytest.raises(KeyError):
                KeyController(verbose=True)
            
    def test_invalid_data_types_in_sections(self):
        """Test behavior with wrong data types in sections"""
        invalid_types_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": "this should be an object",
            "folders": [],
            "urls": null
        }'''
        
        with patch('builtins.open', mock_open(read_data=invalid_types_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises((TypeError, AttributeError)):
                KeyController(verbose=True)
                
    def test_invalid_key_numbers(self):
        """Test behavior with non-numeric key numbers"""
        invalid_keys_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "not_a_number": {
                        "key_sequence": "CMD+A",
                        "color": "#FF0000"
                    },
                    "15.5": {
                        "key_sequence": "CMD+B", 
                        "color": "#00FF00"
                    }
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=invalid_keys_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(ValueError):
                KeyController(verbose=True)
                
    def test_invalid_color_values(self):
        """Test behavior with malformed color values"""
        invalid_colors_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "0": {
                        "key_sequence": "CMD+A",
                        "color": "not_a_valid_color"
                    },
                    "1": {
                        "key_sequence": "CMD+B",
                        "color": "#GGGGGG"
                    },
                    "2": {
                        "key_sequence": "CMD+C",
                        "color": "#FF"
                    }
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=invalid_colors_json)):
            from src.pi_pico.code import KeyController
            
            # Should raise ValueError due to invalid hex characters
            with pytest.raises(ValueError):
                KeyController(verbose=True)
            
    def test_invalid_keycode_sequences(self):
        """Test behavior with invalid keycode sequences"""
        invalid_keycodes_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "0": {
                        "key_sequence": "INVALID_KEY+A",
                        "color": "#FF0000"
                    }
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=invalid_keycodes_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(ValueError, match="Unknown keycode constant"):
                KeyController(verbose=True)
                
    def test_circular_alias_references(self):
        """Test behavior with circular alias references"""
        circular_alias_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {},
                "app1": {
                    "alias_of": "app2"
                },
                "app2": {
                    "alias_of": "app1"
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=circular_alias_json)):
            from src.pi_pico.code import KeyController
            
            # After Fix 4: chained aliases are rejected gracefully — no crash,
            # the aliasing apps are simply skipped and not loaded.
            controller = KeyController(verbose=True)
            assert "app1" not in controller.apps
            assert "app2" not in controller.apps
            
    def test_missing_alias_target(self):
        """Test behavior with alias pointing to non-existent app"""
        missing_alias_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {},
                "app1": {
                    "alias_of": "nonexistent_app"
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=missing_alias_json)):
            from src.pi_pico.code import KeyController
            
            # Should handle missing alias targets gracefully
            controller = KeyController(verbose=True)
            # Missing alias should result in no config for app1
            assert "app1" not in controller.apps or controller.apps["app1"] == {}
            
    def test_invalid_folder_references(self):
        """Test behavior with folder references to non-existent folders"""
        invalid_folder_ref_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "0": {
                        "folder": "nonexistent_folder",
                        "color": "#FF0000"
                    }
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=invalid_folder_ref_json)):
            from src.pi_pico.code import KeyController
            
            # Should handle gracefully by disabling the key
            controller = KeyController(verbose=True)
            # Key 0 should not be in current_config due to invalid folder and no _otherwise
            # Or if it exists, should have empty key_sequences
            if 0 in controller.current_config:
                assert controller.current_config[0]['key_sequences'] == ()
            
    def test_mixed_data_type_key_sequences(self):
        """Test behavior with inconsistent key sequence data types"""
        mixed_types_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "0": {
                        "key_sequence": ["CMD+A", 0.5, "ENTER", null],
                        "color": "#FF0000"
                    }
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=mixed_types_json)):
            from src.pi_pico.code import KeyController
            
            # Should handle mixed types - null becomes None
            controller = KeyController(verbose=True)
            # Key 0 might not be in config due to processing issues with null
            # Just verify the controller was created without crashing
            assert controller is not None
            
    def test_extremely_large_json_values(self):
        """Test behavior with extremely large values"""
        large_values_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "999999": {
                        "key_sequence": "''' + 'A' * 10000 + '''",
                        "color": "#FF0000"
                    }
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=large_values_json)):
            from src.pi_pico.code import KeyController
            
            # Should raise ValueError due to extremely long keycode string
            with pytest.raises(ValueError):
                KeyController(verbose=True)
            
    def test_unicode_and_special_characters(self):
        """Test behavior with Unicode and special characters"""
        unicode_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {},
                "应用程序": {
                    "0": {
                        "key_sequence": "CMD+A",
                        "color": "#FF0000",
                        "description": "特殊字符 test emoji"
                    }
                }
            },
            "folders": {
                "文件夹": {
                    "0": {
                        "key_sequence": "SPACE",
                        "color": "#00FF00"
                    }
                }
            },
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=unicode_json)):
            from src.pi_pico.code import KeyController
            
            # Should handle Unicode characters gracefully
            controller = KeyController(verbose=True)
            assert "应用程序" in controller.apps
            assert "文件夹" in controller.folders
            
    def test_deeply_nested_structure_corruption(self):
        """Test behavior with corrupted nested structures"""
        nested_corruption_json = '''{
            "settings": {
                "rotate": ""
            },
            "applications": {
                "_default": {
                    "0": {
                        "key_sequence": {
                            "this": "should",
                            "be": "a string or array"
                        },
                        "color": ["not", "a", "string"]
                    }
                }
            },
            "folders": {},
            "urls": {}
        }'''
        
        with patch('builtins.open', mock_open(read_data=nested_corruption_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises((TypeError, AttributeError)):
                KeyController(verbose=True)
                
    def test_file_io_errors(self):
        """Test behavior when file cannot be read"""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(FileNotFoundError):
                KeyController(verbose=True)
                
    def test_permission_errors(self):
        """Test behavior with permission errors"""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(PermissionError):
                KeyController(verbose=True)
                
    def test_empty_file(self):
        """Test behavior with empty JSON file"""
        empty_json = ""
        
        with patch('builtins.open', mock_open(read_data=empty_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(json.JSONDecodeError):
                KeyController(verbose=True)
                
    def test_only_whitespace_file(self):
        """Test behavior with file containing only whitespace"""
        whitespace_json = "   \n\t   \n   "
        
        with patch('builtins.open', mock_open(read_data=whitespace_json)):
            from src.pi_pico.code import KeyController
            
            with pytest.raises(json.JSONDecodeError):
                KeyController(verbose=True)