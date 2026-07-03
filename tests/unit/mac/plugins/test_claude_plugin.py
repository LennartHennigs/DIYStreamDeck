"""Tests for the claude plugin — traffic-light feedback for Claude Code hooks.

The claude plugin runs a background Unix-socket listener; on receipt of
'green' | 'red' | 'yellow', it sends a `Claude: <color>` line to the Pico
via the send_to_keypad callable provided by the watchdog at
on_watchdog_start().
"""
import sys
import os
import json
import socket

import pytest

# Add project root to sys.path so imports work during tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from src.mac.plugins.claude import ClaudePlugin
from tests.conftest import wait_for


def _write_config(path, socket_path, **extra):
    """Write a claude.json config with the socket path and optional extras."""
    cfg = {"socket_path": socket_path, **extra}
    path.write_text(json.dumps(cfg))
    return str(path)


@pytest.fixture
def claude_plugin(tmp_path, short_socket_path):
    """A ClaudePlugin whose socket lives at short_socket_path (see conftest)."""
    cfg = _write_config(tmp_path / "claude.json", short_socket_path)
    plugin = ClaudePlugin(cfg, verbose=False)
    yield plugin
    try:
        plugin.on_watchdog_stop()
    except Exception:
        pass


@pytest.fixture
def started_plugin(claude_plugin):
    """Plugin already started with a recording sender. Yields (plugin, sends)."""
    sends = []
    claude_plugin.on_watchdog_start(lambda line: sends.append(line))
    return claude_plugin, sends


def _send_datagram(socket_path: str, msg: str) -> None:
    """Fire a single datagram at the socket."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        s.settimeout(0.5)
        s.sendto(msg.encode(), socket_path)
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Command surface — keypad-triggerable test commands
# ---------------------------------------------------------------------------

def test_commands_expose_three_colors(claude_plugin):
    """Plugin must expose claude.green, claude.red, claude.yellow."""
    commands = claude_plugin.commands()
    assert set(commands) == {"claude.green", "claude.red", "claude.yellow"}


@pytest.mark.parametrize("color", ["green", "red", "yellow"])
def test_command_sends_claude_line(started_plugin, color):
    plugin, sends = started_plugin
    plugin.commands()[f"claude.{color}"]()
    assert sends == [f"Claude: {color}\n"]


# ---------------------------------------------------------------------------
# Socket relay — external hook writes to socket, plugin forwards to keypad
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("color", ["green", "red", "yellow"])
def test_socket_datagram_relays_color(started_plugin, short_socket_path, color):
    _, sends = started_plugin
    _send_datagram(short_socket_path, color)
    assert wait_for(lambda: sends == [f"Claude: {color}\n"]), (
        f"Expected 'Claude: {color}\\n' relayed via socket; got {sends!r}"
    )


@pytest.mark.parametrize("payload,expected", [
    ("purple", ["Claude: green\n"]),   # unknown color word
    ("",      ["Claude: green\n"]),    # empty datagram
    (" green\n", ["Claude: green\n", "Claude: green\n"]),  # whitespace-stripped: still valid
])
def test_socket_bad_payload_handling(started_plugin, short_socket_path, payload, expected):
    """Unknown / empty payloads are dropped; whitespace is stripped so it still parses.

    Followed by a valid 'green' to prove the listener stayed healthy.
    """
    _, sends = started_plugin
    _send_datagram(short_socket_path, payload)
    _send_datagram(short_socket_path, "green")
    assert wait_for(lambda: sends == expected), f"got {sends!r}"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def test_start_creates_socket_file(claude_plugin, short_socket_path):
    claude_plugin.on_watchdog_start(lambda line: None)
    assert wait_for(lambda: os.path.exists(short_socket_path))


def test_stop_removes_socket_file(claude_plugin, short_socket_path):
    claude_plugin.on_watchdog_start(lambda line: None)
    wait_for(lambda: os.path.exists(short_socket_path))
    claude_plugin.on_watchdog_stop()
    assert wait_for(lambda: not os.path.exists(short_socket_path))


def test_stop_stops_listener_thread(claude_plugin, short_socket_path):
    claude_plugin.on_watchdog_start(lambda line: None)
    wait_for(lambda: os.path.exists(short_socket_path))
    thread = claude_plugin._thread
    claude_plugin.on_watchdog_stop()
    if thread is not None:
        thread.join(timeout=1.0)
        assert not thread.is_alive()


def test_start_unlinks_stale_socket_file(tmp_path, short_socket_path):
    """A stale socket file from a prior crash must be cleaned up on start()."""
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    stale.bind(short_socket_path)
    stale.close()
    assert os.path.exists(short_socket_path)

    cfg = _write_config(tmp_path / "claude.json", short_socket_path)
    plugin = ClaudePlugin(cfg, verbose=False)
    try:
        sends = []
        plugin.on_watchdog_start(lambda line: sends.append(line))
        assert wait_for(lambda: os.path.exists(short_socket_path))
        _send_datagram(short_socket_path, "green")
        assert wait_for(lambda: sends == ["Claude: green\n"])
    finally:
        plugin.on_watchdog_stop()


def test_stop_can_be_called_multiple_times(claude_plugin):
    claude_plugin.on_watchdog_start(lambda line: None)
    claude_plugin.on_watchdog_stop()
    claude_plugin.on_watchdog_stop()  # must not raise


def test_stop_without_start_does_not_raise(claude_plugin):
    """on_watchdog_stop() before on_watchdog_start() must be safe."""
    claude_plugin.on_watchdog_stop()


# ---------------------------------------------------------------------------
# Config & safety
# ---------------------------------------------------------------------------

def test_signal_without_start_is_no_op(claude_plugin):
    """Calling claude.* commands before start() must not raise."""
    claude_plugin.commands()["claude.green"]()


def test_config_defaults_when_socket_path_omitted(tmp_path):
    """Missing socket_path in config must fall back to the class default."""
    cfg = tmp_path / "claude.json"
    cfg.write_text(json.dumps({}))
    plugin = ClaudePlugin(str(cfg), verbose=False)
    assert plugin.socket_path == ClaudePlugin.DEFAULT_SOCKET_PATH


def test_listen_for_hooks_disabled_skips_socket(tmp_path, short_socket_path):
    """listen_for_hooks=false must skip socket bind but keep commands working."""
    cfg = _write_config(tmp_path / "claude.json", short_socket_path, listen_for_hooks=False)
    plugin = ClaudePlugin(cfg, verbose=False)
    sends = []
    plugin.on_watchdog_start(lambda line: sends.append(line))
    try:
        assert plugin._sock is None
        assert plugin._thread is None
        # Socket file must not exist
        assert not os.path.exists(short_socket_path)
        # But keypad commands still work
        plugin.commands()["claude.green"]()
        assert sends == ["Claude: green\n"]
    finally:
        plugin.on_watchdog_stop()
