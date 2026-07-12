"""Pico unit-test fixtures."""
import time

import pytest

_real_sleep = time.sleep


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    """Cap real sleeps at 1 ms.

    The firmware sleeps for real HID timing (25 ms after each key sequence,
    per-character string delays) — meaningless in unit tests, and worse:
    macOS App Nap defers sleep timers of backgrounded pytest runs for
    *minutes*, which made every keypress-path test look hung. A capped sleep
    still advances time.monotonic() for the heartbeat tests, and tests that
    patch time.sleep themselves override this fixture as before.
    """
    monkeypatch.setattr(time, "sleep", lambda seconds: _real_sleep(min(seconds, 0.001)))
