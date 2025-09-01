import sys
import os
import pytest
import subprocess

# Add project root to sys.path so imports work during tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from src.mac.plugins.base_plugin import BasePlugin


class DummyPlugin(BasePlugin):
    def commands(self):
        return {}


def test_ping_invalid_ip(monkeypatch):
    dp = DummyPlugin()
    assert dp._ping('not-an-ip') is False


def test_ping_unreachable_ip(monkeypatch):
    # Simulate subprocess.run returning non-zero returncode
    class DummyResult:
        returncode = 1

    def fake_run(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr(subprocess, 'run', fake_run)
    dp = DummyPlugin()
    assert dp._ping('192.0.2.1') is False


def test_ping_reachable_ip(monkeypatch):
    class DummyResult:
        returncode = 0

    def fake_run(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr(subprocess, 'run', fake_run)
    dp = DummyPlugin()
    assert dp._ping('198.51.100.1') is True
