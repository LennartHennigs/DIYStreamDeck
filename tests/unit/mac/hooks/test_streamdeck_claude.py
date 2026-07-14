"""Tests for the streamdeck-claude Claude Code hook."""
import sys
import os
import json
import socket
import subprocess
import threading
import time

import pytest

from tests.conftest import wait_for

HOOK_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../src/mac/hooks/streamdeck-claude.py")
)

# Short timeout for negative-path tests: by the time subprocess.run returns,
# the hook has already done all it will do. A tiny drain window catches any
# stragglers without wasting wall-clock time.
NEGATIVE_DRAIN_S = 0.03


class _Listener:
    """Bind a SOCK_DGRAM socket at `path` and collect received datagrams."""

    def __init__(self, path):
        self.path = path
        self.received = []
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        # short timeout: close() can only join once recvfrom wakes, so this
        # bounds every test's teardown time
        self._sock.settimeout(0.05)
        self._sock.bind(path)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._stop = threading.Event()
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                data, _ = self._sock.recvfrom(64)
                self.received.append(data.decode("utf-8"))
            except socket.timeout:
                continue
            except OSError:
                return

    def close(self):
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=1.0)


def _run_hook(payload_json: str, socket_path: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["STREAMDECK_CLAUDE_SOCKET"] = socket_path
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=payload_json,
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )


@pytest.fixture
def listener(short_socket_path):
    l = _Listener(short_socket_path)
    yield l
    l.close()


# ---------------------------------------------------------------------------
# Happy path: each event → correct color
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("event,signal", [
    ("Stop", "green"),
    ("Notification", "red"),
    ("StopFailure", "yellow"),
    ("UserPromptSubmit", "clear"),
])
def test_event_sends_correct_signal(listener, event, signal):
    payload = json.dumps({"hook_event_name": event})
    _run_hook(payload, listener.path)
    assert wait_for(lambda: listener.received == [signal]), (
        f"expected [{signal!r}] after {event}; got {listener.received!r}"
    )


# ---------------------------------------------------------------------------
# Silent-on-failure — the five hook-visible cases
# ---------------------------------------------------------------------------

def _assert_clean_exit(result):
    """Hook must exit 0 with no traceback on stderr."""
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def _assert_silent(result, listener):
    """Hook must exit cleanly and produce no datagrams."""
    _assert_clean_exit(result)
    time.sleep(NEGATIVE_DRAIN_S)
    assert listener.received == []


def test_unknown_event_is_silent(listener):
    """Events not in the mapping (PreToolUse, etc.) must not send anything."""
    result = _run_hook(json.dumps({"hook_event_name": "PreToolUse"}), listener.path)
    _assert_silent(result, listener)


def test_missing_socket_is_silent(short_socket_path):
    """No listener bound → hook must exit cleanly, no exception on stderr."""
    result = _run_hook(json.dumps({"hook_event_name": "Stop"}), short_socket_path)
    _assert_clean_exit(result)


def test_bad_json_is_silent(listener):
    """Malformed stdin must be caught, not propagated."""
    result = _run_hook("not json at all", listener.path)
    _assert_silent(result, listener)


def test_empty_stdin_is_silent(listener):
    result = _run_hook("", listener.path)
    _assert_silent(result, listener)


def test_non_dict_payload_is_silent(listener):
    """A JSON array or scalar is well-formed JSON but wrong shape."""
    result = _run_hook("[1,2,3]", listener.path)
    _assert_silent(result, listener)


def test_missing_event_name_is_silent(listener):
    """Payload without hook_event_name key must be dropped, not crash."""
    result = _run_hook(json.dumps({"some_other_field": "value"}), listener.path)
    _assert_silent(result, listener)
