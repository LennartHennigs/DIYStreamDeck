"""Tests for the `Claude:` serial handler on the Pico.

The Pico receives `Claude: green|red|yellow` lines from the Mac watchdog
(pushed by the claude plugin's socket relay). On receipt it must:
- Flood-fill all keys with the color's RGB tuple.
- Remember the color as sticky state (`_flash_deadline`) — it does NOT
  fade after a timeout; the color IS the Claude Code status signal.
- Get cleared (and the layout repainted) by any deliberate ack:
  App: line, Rotate: line, HELLO: handshake, or a keypress.
- NOT get cleared by `Terminated:` (app death isn't user ack).
- Ignore unknown colors.

`_flash_deadline` is the git-blame-continuous name that used to hold a
monotonic-time deadline. It now holds either the RGB tuple currently on
the LEDs, or None. The rename cost wasn't worth the churn.
"""
import sys
import os
from unittest.mock import patch, mock_open

import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

# Trigger the CircuitPython mocks
from tests.unit.pico.mock_circuitpython import MockUSBCDC  # noqa: F401


CLAUDE_TEST_CONFIG = '''{
    "settings": {"rotate": ""},
    "applications": {
        "_otherwise": {
            "0": {
                "key_sequence": "CMD+C",
                "color": "#00FF00",
                "description": "Copy"
            }
        }
    },
    "folders": {},
    "urls": {}
}'''


class TestClaudeSerialHandler:

    @patch('builtins.open', mock_open(read_data=CLAUDE_TEST_CONFIG))
    def setup_method(self, method):
        from src.pi_pico.code import KeyController
        self.controller = KeyController(verbose=False)

    def _key_colors(self):
        """Return the last color each key was set to."""
        return [getattr(k, "led_color", None) for k in self.controller.keys]

    # ------------------------------------------------------------------
    # Flood-fill
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("color", ["green", "red", "yellow"])
    def test_claude_lights_all_keys(self, color):
        """Claude: <color> must flood-fill every key with the mapped RGB."""
        self.controller.process_serial_str(f"Claude: {color}")
        from src.pi_pico.code import FLASH_COLORS
        expected = FLASH_COLORS[color]
        for k in self.controller.keys:
            assert getattr(k, "led_color", None) == expected, (
                f"Every key must be lit {color}; got {self._key_colors()}"
            )

    def test_claude_case_insensitive(self):
        """Colors must match case-insensitively so 'GREEN' works too."""
        self.controller.process_serial_str("Claude: GREEN")
        from src.pi_pico.code import FLASH_COLORS
        for k in self.controller.keys:
            assert getattr(k, "led_color", None) == FLASH_COLORS["green"]

    def test_claude_unknown_color_ignored(self):
        """Unknown color words must NOT set sticky state or repaint keys."""
        initial_colors = self._key_colors()
        self.controller._flash_deadline = None
        self.controller.process_serial_str("Claude: mauve")
        assert self.controller._flash_deadline is None, (
            "unknown colors must not set sticky state"
        )
        assert self._key_colors() == initial_colors

    # ------------------------------------------------------------------
    # Sticky state semantics
    # ------------------------------------------------------------------

    def test_sticky_state_none_by_default(self):
        """New controller must have _flash_deadline is None (no active signal)."""
        assert self.controller._flash_deadline is None

    def test_claude_sets_sticky_color(self):
        """Claude: <color> must store the RGB tuple as sticky state."""
        from src.pi_pico.code import FLASH_COLORS
        self.controller.process_serial_str("Claude: red")
        assert self.controller._flash_deadline == FLASH_COLORS["red"]

    def test_second_claude_overrides_sticky_color(self):
        """A new Claude: overwrites the previous sticky color."""
        from src.pi_pico.code import FLASH_COLORS
        self.controller.process_serial_str("Claude: green")
        assert self.controller._flash_deadline == FLASH_COLORS["green"]
        self.controller.process_serial_str("Claude: red")
        assert self.controller._flash_deadline == FLASH_COLORS["red"]
        for k in self.controller.keys:
            assert getattr(k, "led_color", None) == FLASH_COLORS["red"]

    # ------------------------------------------------------------------
    # Ack sites — deliberate interactions clear sticky state
    # ------------------------------------------------------------------

    def test_app_clears_sticky_state(self):
        """App: line clears the sticky signal and repaints the layout."""
        self.controller.process_serial_str("Claude: green")
        assert self.controller._flash_deadline is not None
        self.controller.process_serial_str("App: Safari")
        assert self.controller._flash_deadline is None, (
            "App: must clear the sticky signal"
        )

    def test_rotate_clears_sticky_state(self):
        """Rotate: line clears the sticky signal."""
        self.controller.process_serial_str("Claude: red")
        assert self.controller._flash_deadline is not None
        self.controller.process_serial_str("Rotate: CW")
        assert self.controller._flash_deadline is None, (
            "Rotate: must clear the sticky signal"
        )

    def test_hello_clears_sticky_state(self):
        """HELLO: handshake clears the sticky signal (fresh session)."""
        self.controller.process_serial_str("Claude: yellow")
        assert self.controller._flash_deadline is not None
        self.controller.process_serial_str("HELLO:1.0")
        assert self.controller._flash_deadline is None, (
            "HELLO: must clear the sticky signal"
        )

    def test_keypress_clears_sticky_state_and_repaints(self):
        """A keypress on a configured key clears sticky state and repaints."""
        self.controller.process_serial_str("Claude: green")
        assert self.controller._flash_deadline is not None
        # Simulate a press on key 0 (configured for CMD+C in the test JSON).
        key = self.controller.keys[0]
        self.controller.key_press_action(key)
        assert self.controller._flash_deadline is None, (
            "keypress must clear the sticky signal"
        )

    def test_keypress_on_unbound_key_does_not_change_state(self):
        """An unbound key falls out of key_press_action early — no ack."""
        self.controller.process_serial_str("Claude: red")
        # Key 5 is not in the test config
        key = self.controller.keys[5]
        self.controller.key_press_action(key)
        # Unbound press returns before the ack — sticky signal survives
        assert self.controller._flash_deadline is not None, (
            "unbound keypress should not act as ack (early return before "
            "the clear-sticky block)"
        )

    # ------------------------------------------------------------------
    # Non-ack messages
    # ------------------------------------------------------------------

    def test_terminated_does_not_clear_sticky_state(self):
        """Terminated: is not user ack — sticky signal must survive."""
        from src.pi_pico.code import FLASH_COLORS
        self.controller.process_serial_str("Claude: red")
        self.controller.process_serial_str("Terminated: Safari")
        assert self.controller._flash_deadline == FLASH_COLORS["red"], (
            "Terminated: must NOT clear the sticky signal"
        )

    def test_heartbeat_does_not_clear_sticky_state(self):
        """HB heartbeat is not user ack — sticky signal must survive."""
        from src.pi_pico.code import FLASH_COLORS
        self.controller.process_serial_str("Claude: yellow")
        self.controller.process_serial_str("HB")
        assert self.controller._flash_deadline == FLASH_COLORS["yellow"]

    def test_claude_does_not_break_heartbeat(self):
        """A Claude: signal must not touch last_heartbeat."""
        before = self.controller.last_heartbeat
        self.controller.process_serial_str("Claude: green")
        assert self.controller.last_heartbeat == before

    def test_claude_does_not_change_unloaded_flag(self):
        self.controller.unloaded = False
        self.controller.process_serial_str("Claude: green")
        assert self.controller.unloaded is False
