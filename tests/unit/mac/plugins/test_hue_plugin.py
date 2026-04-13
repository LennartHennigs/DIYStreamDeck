"""
Unit tests for Hue plugin
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock


# Mock phue before importing HuePlugin
import sys
sys.modules.setdefault('phue', MagicMock())

from src.mac.plugins.hue import HuePlugin


class TestHuePlugin:
    """Tests for HuePlugin functionality"""

    @pytest.fixture
    def hue_plugin(self, tmp_path, mock_hue_bridge):
        config = {"bridge_ip": "192.168.1.1"}
        config_file = tmp_path / "hue.json"
        config_file.write_text(json.dumps(config))
        with patch("src.mac.plugins.hue.Bridge", return_value=mock_hue_bridge):
            plugin = HuePlugin(str(config_file), verbose=False)
        return plugin

    @pytest.fixture
    def hue_plugin_verbose(self, tmp_path, mock_hue_bridge):
        config = {"bridge_ip": "192.168.1.1"}
        config_file = tmp_path / "hue.json"
        config_file.write_text(json.dumps(config))
        with patch("src.mac.plugins.hue.Bridge", return_value=mock_hue_bridge):
            plugin = HuePlugin(str(config_file), verbose=True)
        return plugin

    # --- commands ---

    def test_commands_registered(self, hue_plugin):
        cmds = hue_plugin.commands()
        assert "hue.turn_on" in cmds
        assert "hue.turn_off" in cmds
        assert "hue.toggle" in cmds

    # --- turn_on by name ---

    def test_turn_on_by_name_targets_matching_light(self, hue_plugin):
        hue_plugin.turn_on("Test Light 1")
        assert hue_plugin.bridge.lights[0].on is True

    def test_turn_on_by_name_does_not_affect_other_lights(self, hue_plugin):
        # light2 starts off=False; turning on light1 by name must not touch light2
        hue_plugin.bridge.lights[1].on = False
        hue_plugin.turn_on("Test Light 1")
        assert hue_plugin.bridge.lights[1].on is False

    def test_turn_on_by_name_case_insensitive(self, hue_plugin):
        hue_plugin.turn_on("test light 1")
        assert hue_plugin.bridge.lights[0].on is True

    # --- turn_on by index ---

    def test_turn_on_by_index_targets_only_that_light(self, hue_plugin):
        """int 0 must turn on only the first light, not all lights."""
        hue_plugin.bridge.lights[0].on = False
        hue_plugin.bridge.lights[1].on = False
        hue_plugin.turn_on(0)
        assert hue_plugin.bridge.lights[0].on is True
        assert hue_plugin.bridge.lights[1].on is False  # ← fails before fix

    def test_turn_on_second_light_by_index(self, hue_plugin):
        """int 1 must turn on only the second light."""
        hue_plugin.bridge.lights[0].on = False
        hue_plugin.bridge.lights[1].on = False
        hue_plugin.turn_on(1)
        assert hue_plugin.bridge.lights[1].on is True
        assert hue_plugin.bridge.lights[0].on is False  # ← fails before fix

    # --- turn_off ---

    def test_turn_off_by_name(self, hue_plugin):
        hue_plugin.bridge.lights[0].on = True
        hue_plugin.turn_off("Test Light 1")
        assert hue_plugin.bridge.lights[0].on is False

    def test_turn_off_by_index_targets_only_that_light(self, hue_plugin):
        hue_plugin.bridge.lights[0].on = True
        hue_plugin.bridge.lights[1].on = True
        hue_plugin.turn_off(0)
        assert hue_plugin.bridge.lights[0].on is False
        assert hue_plugin.bridge.lights[1].on is True  # ← fails before fix

    # --- toggle ---

    def test_toggle_by_name_turns_off_when_on(self, hue_plugin):
        hue_plugin.bridge.lights[0].on = True
        hue_plugin.toggle("Test Light 1")
        assert hue_plugin.bridge.lights[0].on is False

    def test_toggle_by_name_turns_on_when_off(self, hue_plugin):
        hue_plugin.bridge.lights[0].on = False
        hue_plugin.toggle("Test Light 1")
        assert hue_plugin.bridge.lights[0].on is True

    def test_toggle_by_index_targets_only_that_light(self, hue_plugin):
        hue_plugin.bridge.lights[0].on = True
        hue_plugin.bridge.lights[1].on = True
        hue_plugin.toggle(0)
        assert hue_plugin.bridge.lights[0].on is False
        assert hue_plugin.bridge.lights[1].on is True  # ← fails before fix

    # --- unknown light ---

    def test_unknown_light_name_prints_error(self, hue_plugin, capsys):
        hue_plugin.turn_on("Nonexistent Light")
        captured = capsys.readouterr()
        assert "Could not find" in captured.out

    def test_out_of_range_index_prints_error(self, hue_plugin, capsys):
        hue_plugin.turn_on(99)
        captured = capsys.readouterr()
        assert "Could not find" in captured.out

    # --- verbose output ---

    def test_verbose_turn_on_prints_message(self, hue_plugin_verbose, capsys):
        hue_plugin_verbose.turn_on("Test Light 1")
        captured = capsys.readouterr()
        assert "on" in captured.out.lower()

    # --- config errors ---

    def test_missing_config_file_raises(self, tmp_path):
        with patch("src.mac.plugins.hue.Bridge"):
            with pytest.raises(Exception):
                HuePlugin(str(tmp_path / "missing.json"), verbose=False)

    def test_missing_bridge_ip_raises(self, tmp_path):
        config_file = tmp_path / "hue.json"
        config_file.write_text(json.dumps({}))
        with patch("src.mac.plugins.hue.Bridge"):
            with pytest.raises((ValueError, Exception)):
                HuePlugin(str(config_file), verbose=False)
