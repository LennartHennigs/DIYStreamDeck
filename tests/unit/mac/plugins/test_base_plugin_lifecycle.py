"""Tests for the optional lifecycle hooks on BasePlugin."""
import json

import pytest

from src.mac.plugins.base_plugin import BasePlugin


class _MinimalPlugin(BasePlugin):
    """A concrete plugin that only implements `commands()`."""

    def commands(self):
        return {}


@pytest.fixture
def config_file(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({}))
    return str(p)


def test_on_watchdog_start_defaults_to_noop(config_file):
    """BasePlugin must expose `on_watchdog_start(send_to_keypad)` as a no-op."""
    plugin = _MinimalPlugin(config_file, verbose=False)
    assert hasattr(plugin, "on_watchdog_start")
    calls = []
    plugin.on_watchdog_start(lambda line: calls.append(line))
    assert calls == [], "default on_watchdog_start() must not invoke send_to_keypad"


def test_on_watchdog_stop_defaults_to_noop(config_file):
    """BasePlugin must expose `on_watchdog_stop()` as a no-op."""
    plugin = _MinimalPlugin(config_file, verbose=False)
    assert hasattr(plugin, "on_watchdog_stop")
    assert plugin.on_watchdog_stop() is None


def test_on_watchdog_start_accepts_send_callable(config_file):
    """`on_watchdog_start` must take exactly one positional argument."""
    from inspect import signature

    plugin = _MinimalPlugin(config_file, verbose=False)
    sig = signature(plugin.on_watchdog_start)
    params = list(sig.parameters.values())
    assert len(params) == 1, (
        f"on_watchdog_start must take exactly one positional param "
        f"(send_to_keypad); got {params!r}"
    )


def test_existing_plugin_shape_still_works(config_file):
    """A subclass that overrides only `commands()` must stay constructible."""
    plugin = _MinimalPlugin(config_file, verbose=False)
    assert plugin.commands() == {}
    plugin.on_watchdog_start(lambda line: None)
    plugin.on_watchdog_stop()
