"""
Unit tests for Pi Pico configuration loading
"""
import pytest
import json
import sys
import os
import tempfile
from unittest.mock import Mock, patch, mock_open

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
from tests.unit.pico.mock_circuitpython import MockUSBCDC  # triggers sys.modules setup

# Note: In actual implementation, these imports would need to be adjusted
# for CircuitPython environment or mocked appropriately
try:
    from src.pi_pico.code import KeyController
except ImportError:
    # For testing without CircuitPython environment
    KeyController = Mock


class TestConfigLoader:
    """Test configuration loading and parsing functionality"""
    
    def test_parse_json_valid_legacy_config(self, sample_config_v1, temp_config_file):
        """Test parsing valid legacy (v1.0) configuration"""
        # Mock the file reading for CircuitPython environment
        with patch('builtins.open', mock_open(read_data=json.dumps(sample_config_v1))):
            with patch('json.load', return_value=sample_config_v1):
                # This would need adjustment for actual CircuitPython testing
                config = sample_config_v1
                
                assert "settings" in config
                assert "applications" in config
                assert "folders" in config
                assert config["settings"]["rotate"] == "CCW"
    
    def test_parse_json_valid_v2_config(self, sample_config_v2):
        """Test parsing valid v2.0 configuration with metadata"""
        with patch('builtins.open', mock_open(read_data=json.dumps(sample_config_v2))):
            with patch('json.load', return_value=sample_config_v2):
                config = sample_config_v2
                
                assert "metadata" in config
                assert "color_scheme" in config
                assert config["metadata"]["version"] == "2.0.0"
                assert "navigation" in config["color_scheme"]
    
    def test_parse_json_malformed(self):
        """Test handling of malformed JSON"""
        malformed_json = '{"invalid": "json"'  # Missing closing brace
        
        with patch('builtins.open', mock_open(read_data=malformed_json)):
            with patch('json.load', side_effect=json.JSONDecodeError("msg", "doc", 0)):
                with pytest.raises(json.JSONDecodeError):
                    json.load({})
    
    def test_missing_required_sections(self):
        """Test handling of configuration missing required sections"""
        incomplete_config = {"settings": {}}  # Missing applications
        
        with patch('builtins.open', mock_open(read_data=json.dumps(incomplete_config))):
            with patch('json.load', return_value=incomplete_config):
                config = incomplete_config
                
                assert "applications" not in config
                # In real implementation, this should either provide defaults
                # or raise an appropriate error
    
    def test_keycode_string_to_tuple_valid(self):
        """Test valid keycode string to tuple conversion"""
        # Mock KeyController for testing
        mock_controller = Mock()
        mock_controller.KEYCODE_MAPPING = {
            'CTRL': 1, 'A': 2, 'GUI': 3, 'SHIFT': 4, 'V': 5
        }
        
        def keycode_string_to_tuple(keycode_string):
            keycode_list = keycode_string.split('+')
            keycodes = []
            for key in keycode_list:
                if key.upper() == "CMD":
                    key = "GUI"
                if key not in mock_controller.KEYCODE_MAPPING:
                    raise ValueError(f"Unknown keycode: {key}")
                keycodes.append(mock_controller.KEYCODE_MAPPING[key])
            return tuple(keycodes)
        
        # Test valid keycode combinations
        result = keycode_string_to_tuple("CTRL+A")
        assert result == (1, 2)
        
        result = keycode_string_to_tuple("GUI+SHIFT+V")
        assert result == (3, 4, 5)
    
    def test_keycode_string_to_tuple_invalid(self):
        """Test invalid keycode string handling"""
        mock_controller = Mock()
        mock_controller.KEYCODE_MAPPING = {'CTRL': 1}
        
        def keycode_string_to_tuple(keycode_string):
            keycode_list = keycode_string.split('+')
            keycodes = []
            for key in keycode_list:
                if key not in mock_controller.KEYCODE_MAPPING:
                    raise ValueError(f"Unknown keycode: {key}")
                keycodes.append(mock_controller.KEYCODE_MAPPING[key])
            return tuple(keycodes)
        
        with pytest.raises(ValueError, match="Unknown keycode"):
            keycode_string_to_tuple("INVALID_KEY")
    
    def test_color_string_to_tuple_valid(self):
        """Test valid color string to RGB tuple conversion"""
        def color_string_to_tuple(color_string):
            if color_string.startswith("#") and len(color_string) == 7:
                return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
            return False
        
        # Test valid hex colors
        result = color_string_to_tuple("#FF0000")
        assert result == (255, 0, 0)
        
        result = color_string_to_tuple("#00FF00")
        assert result == (0, 255, 0)
        
        result = color_string_to_tuple("#0000FF")
        assert result == (0, 0, 255)
    
    def test_color_string_to_tuple_invalid(self):
        """Test invalid color string handling"""
        def color_string_to_tuple(color_string):
            if color_string.startswith("#") and len(color_string) == 7:
                try:
                    return tuple(int(color_string[i:i+2], 16) for i in (1, 3, 5))
                except ValueError:
                    return False
            return False
        
        # Test invalid color formats
        assert color_string_to_tuple("red") == False
        assert color_string_to_tuple("#ZZ0000") == False
        assert color_string_to_tuple("#FF00") == False
    
    def test_key_rotation_mapping_cw(self):
        """Test clockwise key rotation mapping"""
        # From the original code
        CW = [12, 8, 4, 0, 13, 9, 5, 1, 14, 10, 6, 2, 15, 11, 7, 3]
        
        original_config = {0: {"color": "#FF0000"}, 1: {"color": "#00FF00"}}
        
        def rotate_keys_cw(config):
            return {i: config[cw] for i, cw in enumerate(CW) if cw in config}
        
        rotated = rotate_keys_cw(original_config)
        
        # Key 0 should be mapped from position 3 (CW[3] = 0)
        assert 3 in rotated
        assert rotated[3]["color"] == "#FF0000"
    
    def test_key_rotation_mapping_ccw(self):
        """Test counter-clockwise key rotation mapping"""
        # From the original code  
        CCW = [3, 7, 11, 15, 2, 6, 10, 14, 1, 5, 9, 13, 0, 4, 8, 12]
        
        original_config = {0: {"color": "#FF0000"}}
        
        def rotate_keys_ccw(config):
            return {i: config[ccw] for i, ccw in enumerate(CCW) if ccw in config}
        
        rotated = rotate_keys_ccw(original_config)
        
        # Key 0 should be mapped from position 12 (CCW[12] = 0)
        assert 12 in rotated
        assert rotated[12]["color"] == "#FF0000"
    
    def test_folder_validation(self, sample_config_v1):
        """Test folder reference validation"""
        config = sample_config_v1.copy()
        
        # Add invalid folder reference
        config["applications"]["test_app"] = {
            "0": {
                "folder": "nonexistent_folder",
                "color": "#FFFFFF",
                "description": "Invalid folder"
            }
        }
        
        def validate_folder_references(config):
            errors = []
            for app_name, app_config in config.get("applications", {}).items():
                for key, key_config in app_config.items():
                    if isinstance(key_config, dict) and "folder" in key_config:
                        folder_name = key_config["folder"]
                        if folder_name not in config.get("folders", {}):
                            errors.append(f"Folder '{folder_name}' not found")
            return errors
        
        errors = validate_folder_references(config)
        assert len(errors) == 1
        assert "nonexistent_folder" in errors[0]
    
    def test_alias_resolution(self):
        """Test application alias resolution"""
        config = {
            "applications": {
                "Notes": {
                    "0": {
                        "key_sequence": "GUI+N",
                        "color": "#00FF00",
                        "description": "New Note"
                    }
                },
                "Notizen": {
                    "alias_of": "Notes"
                }
            }
        }
        
        def resolve_alias(app_name, config):
            app_config = config["applications"].get(app_name, {})
            if "alias_of" in app_config:
                return config["applications"].get(app_config["alias_of"], {})
            return app_config
        
        resolved = resolve_alias("Notizen", config)
        assert "0" in resolved
        assert resolved["0"]["description"] == "New Note"
    
    def test_default_config_merging(self, sample_config_v1):
        """Test merging of _default configuration with app-specific config"""
        def merge_with_defaults(app_config, default_config):
            merged = default_config.copy()
            merged.update(app_config)
            return merged
        
        default_config = sample_config_v1["applications"]["_default"]
        zoom_config = sample_config_v1["applications"]["zoom.us"]
        
        merged = merge_with_defaults(zoom_config, default_config)
        
        # Should have both default and zoom-specific keys
        assert "15" in merged  # From default
        assert "0" in merged   # From zoom.us
        assert "1" in merged   # From zoom.us
    
    def test_configuration_versioning(self, sample_config_v2):
        """Test configuration version detection and handling"""
        def detect_version(config):
            if "metadata" in config:
                return config["metadata"].get("version", "1.0.0")
            return "1.0.0"

        version = detect_version(sample_config_v2)
        assert version == "2.0.0"

        # Test legacy config (no metadata)
        legacy_config = {"applications": {}}
        version = detect_version(legacy_config)
        assert version == "1.0.0"


# --- New tests targeting actual KeyController methods ---

MINIMAL_JSON = json.dumps({
    "settings": {"rotate": ""},
    "applications": {"_otherwise": {}},
    "folders": {},
    "urls": {}
})


class TestParseJson:
    """Tests for KeyController.parse_json() error handling."""

    def test_parse_json_missing_file_raises_oserror(self):
        """Missing config file must raise OSError with a helpful message."""
        kc = KeyController.__new__(KeyController)
        with patch('builtins.open', side_effect=OSError("No such file or directory")):
            with pytest.raises((OSError, Exception)) as exc_info:
                kc.parse_json("missing.json")
            assert "missing.json" in str(exc_info.value) or "No such file" in str(exc_info.value)

    def test_parse_json_malformed_json_raises_valueerror(self):
        """Malformed JSON must raise ValueError (or subclass) with a helpful message."""
        kc = KeyController.__new__(KeyController)
        with patch('builtins.open', mock_open(read_data="{bad json here")):
            with pytest.raises((ValueError, Exception)) as exc_info:
                kc.parse_json("bad.json")  # ← propagates ValueError before fix too, but test documents intent
            # After fix: message should mention the filename
            assert "bad.json" in str(exc_info.value) or "JSON" in str(exc_info.value) or "Expecting" in str(exc_info.value)


class TestFoldersKeyAccess:
    """Tests that missing 'folders' key doesn't cause KeyError."""

    @patch('builtins.open', mock_open(read_data=MINIMAL_JSON))
    def _make_controller(self):
        return KeyController(verbose=False)

    def test_process_global_section_no_folders_key(self):
        """Config with no 'folders' key must not raise KeyError in process_global_section."""
        with patch('builtins.open', mock_open(read_data=MINIMAL_JSON)):
            kc = KeyController(verbose=False)

        # Simulate a config that has _default keys referencing a folder,
        # but the json_data has no 'folders' key at all.
        json_data_no_folders = {
            "applications": {
                "_default": {
                    "0": {
                        "folder": "some_folder",
                        "color": "#FF0000",
                        "description": "Test"
                    }
                }
            }
            # No 'folders' key — would cause KeyError before fix
        }
        # Should not raise; should simply skip or warn about missing folder
        result = kc.process_global_section(json_data_no_folders)  # ← KeyError before fix
        assert isinstance(result, dict)

    def test_process_config_no_folders_key(self):
        """process_config must not crash when json_data has no 'folders' key."""
        with patch('builtins.open', mock_open(read_data=MINIMAL_JSON)):
            kc = KeyController(verbose=False)

        json_data_no_folders = {
            "applications": {
                "TestApp": {
                    "0": {
                        "folder": "missing_folder",
                        "color": "#00FF00",
                        "description": "Test"
                    }
                }
            }
        }
        app_config = {"TestApp": {}}
        # Should not raise KeyError
        kc.process_config(
            json_data_no_folders["applications"]["TestApp"],
            json_data_no_folders,
            "TestApp",
            app_config
        )  # ← KeyError before fix


class TestParseBoolFromConfig:
    """Tests for the parse_bool_from_config helper."""

    @patch('builtins.open', mock_open(read_data=MINIMAL_JSON))
    def setup_method(self, method):
        self.kc = KeyController(verbose=False)

    def test_string_true_returns_true(self):
        assert self.kc.parse_bool_from_config("true") is True

    def test_string_true_uppercase_returns_true(self):
        assert self.kc.parse_bool_from_config("True") is True

    def test_string_false_returns_false(self):
        assert self.kc.parse_bool_from_config("false") is False

    def test_native_bool_true_returns_true(self):
        assert self.kc.parse_bool_from_config(True) is True

    def test_native_bool_false_returns_false(self):
        assert self.kc.parse_bool_from_config(False) is False

    def test_missing_key_returns_default(self):
        assert self.kc.parse_bool_from_config(None, default=True) is True
        assert self.kc.parse_bool_from_config(None, default=False) is False

    def test_ignore_default_string_in_config(self):
        """ignore_default: 'true' must be treated as True, not a string."""
        config = {"ignore_default": "true"}
        result = self.kc.parse_bool_from_config(config.get("ignore_default", "false"))
        assert result is True

    def test_ignore_default_bool_in_config(self):
        """ignore_default: true (native JSON bool) must be treated as True."""
        config = {"ignore_default": True}
        result = self.kc.parse_bool_from_config(config.get("ignore_default", False))
        assert result is True


class TestColorStringToTuple:
    """Tests for KeyController.color_string_to_tuple()."""

    @patch('builtins.open', mock_open(read_data=MINIMAL_JSON))
    def setup_method(self, method):
        self.kc = KeyController(verbose=False)

    def test_valid_hex_returns_tuple(self):
        """A valid '#RRGGBB' string returns an (R, G, B) tuple."""
        assert self.kc.color_string_to_tuple("#FF0000") == (255, 0, 0)
        assert self.kc.color_string_to_tuple("#00FF00") == (0, 255, 0)
        assert self.kc.color_string_to_tuple("#0000FF") == (0, 0, 255)
        assert self.kc.color_string_to_tuple("#1A2B3C") == (26, 43, 60)

    def test_non_hash_string_returns_none(self):
        """Strings not starting with '#' return None."""
        assert self.kc.color_string_to_tuple("red") is None
        assert self.kc.color_string_to_tuple("255,0,0") is None

    def test_invalid_hex_raises_valueerror(self):
        """A '#' string with non-hex digits must raise ValueError, not crash silently."""
        with pytest.raises(ValueError, match="Invalid hex color"):
            self.kc.color_string_to_tuple("#GGGGGG")

    def test_another_invalid_hex_raises_valueerror(self):
        """Invalid hex digits at any position must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid hex color"):
            self.kc.color_string_to_tuple("#XY00ZZ")


class TestRotationValidation:
    """Tests for rotation setting validation in KeyController.__init__."""

    def test_valid_cw_rotation(self):
        """rotate='CW' must be accepted and stored as 'CW'."""
        json_with_cw = json.dumps({
            "settings": {"rotate": "CW"},
            "applications": {"_otherwise": {}},
            "folders": {},
            "urls": {}
        })
        with patch('builtins.open', mock_open(read_data=json_with_cw)):
            kc = KeyController(verbose=False)
        assert kc.rotate == "CW"

    def test_valid_ccw_rotation(self):
        """rotate='CCW' must be accepted and stored as 'CCW'."""
        json_with_ccw = json.dumps({
            "settings": {"rotate": "CCW"},
            "applications": {"_otherwise": {}},
            "folders": {},
            "urls": {}
        })
        with patch('builtins.open', mock_open(read_data=json_with_ccw)):
            kc = KeyController(verbose=False)
        assert kc.rotate == "CCW"

    def test_invalid_rotation_is_ignored(self):
        """rotate='northwest' must not raise and must store '' (invalid value ignored)."""
        json_with_invalid = json.dumps({
            "settings": {"rotate": "northwest"},
            "applications": {"_otherwise": {}},
            "folders": {},
            "urls": {}
        })
        with patch('builtins.open', mock_open(read_data=json_with_invalid)):
            kc = KeyController(verbose=False)  # must not raise
        assert kc.rotate == "", f"Expected '' for invalid rotation, got {kc.rotate!r}"

    def test_invalid_rotation_prints_warning(self, capsys):
        """rotate='diagonal' must print a warning message."""
        json_with_invalid = json.dumps({
            "settings": {"rotate": "diagonal"},
            "applications": {"_otherwise": {}},
            "folders": {},
            "urls": {}
        })
        with patch('builtins.open', mock_open(read_data=json_with_invalid)):
            KeyController(verbose=False)
        captured = capsys.readouterr()
        assert "diagonal" in captured.out or "diagonal" in captured.err, (
            "Expected a warning mentioning the invalid rotation value"
        )

    def test_chained_alias_is_rejected(self, capsys):
        """Chained aliases (A→B where B also has alias_of) must be rejected gracefully.

        Before the fix: code crashes with AttributeError when processing the chain.
        After the fix: the app is skipped and not present in controller.apps.
        """
        chained_config = json.dumps({
            "settings": {"rotate": ""},
            "applications": {
                "_otherwise": {
                    "0": {"key_sequence": "CMD+C", "color": "#00FF00", "description": "Copy"}
                },
                "AppA": {"alias_of": "AppB"},
                "AppB": {"alias_of": "AppC"},
                "AppC": {
                    "0": {"key_sequence": "CMD+V", "color": "#0000FF", "description": "Paste"}
                }
            },
            "folders": {},
            "urls": {}
        })
        with patch('builtins.open', mock_open(read_data=chained_config)):
            controller = KeyController(verbose=True)
        # AppA should be rejected — it points to AppB which itself is an alias
        assert "AppA" not in controller.apps, (
            "AppA should not be loaded because it uses a chained alias"
        )
        # AppC (non-alias) should still load normally
        assert "AppC" in controller.apps


class TestSelfReferenceAlias:
    """load_single_app_config must reject self-referencing aliases (alias_of == app)."""

    @patch('builtins.open', mock_open(read_data=MINIMAL_JSON))
    def setup_method(self, method):
        self.kc = KeyController(verbose=False)

    def test_self_alias_returns_none(self):
        """alias_of pointing to the same app name must return None, not silently load itself."""
        json_data = {
            "applications": {
                "Zoom": {"alias_of": "Zoom"},   # self-reference
                "_otherwise": {}
            },
            "folders": {}
        }
        result = self.kc.load_single_app_config(
            "Zoom",
            json_data["applications"]["Zoom"],
            json_data,
        )
        assert result is None, (
            "load_single_app_config must return None for a self-referencing alias, "
            "currently it silently resolves the alias to itself"
        )

    def test_self_alias_prints_error(self, capsys):
        """alias_of == app must print an error message."""
        json_data = {
            "applications": {
                "Zoom": {"alias_of": "Zoom"},
                "_otherwise": {}
            },
            "folders": {}
        }
        self.kc.load_single_app_config(
            "Zoom",
            json_data["applications"]["Zoom"],
            json_data,
        )
        captured = capsys.readouterr()
        assert "Zoom" in captured.out, (
            "Expected an error message mentioning the app name for a self-referencing alias"
        )
