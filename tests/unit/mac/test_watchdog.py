"""
Unit tests for Mac watchdog script.

Two categories:
1. Source-inspection tests — no import required (Cocoa unavailable in test env)
2. Functional tests — stub out Cocoa/objc at sys.modules level, then import the
   real module and exercise methods directly.
"""
import re
import os
import sys
import time
import types
import threading
import argparse
from unittest.mock import MagicMock, patch, call


WATCHDOG_SRC = os.path.join(
    os.path.dirname(__file__), '../../../src/mac/watchdog.py'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_source():
    with open(WATCHDOG_SRC, 'r') as f:
        return f.read()


def _stub_cocoa_modules():
    """Inject minimal stubs so watchdog.py can be imported without macOS frameworks.

    Cocoa.NSObject must be a *real* Python class (not a MagicMock) so that
    `class WatchDog(Cocoa.NSObject)` produces a proper type we can instantiate.
    """
    # serial — needs a real SerialException so except-clauses match correctly
    if 'serial' not in sys.modules:
        serial_mod = types.ModuleType('serial')
        serial_mod.SerialException = type('SerialException', (OSError,), {})
        serial_mod.Serial = MagicMock
        sys.modules['serial'] = serial_mod

    # Cocoa — NSObject must be a real class; everything else can be a MagicMock
    if 'Cocoa' not in sys.modules:
        cocoa_mod = types.ModuleType('Cocoa')

        class NSObjectStub:
            pass

        cocoa_mod.NSObject = NSObjectStub
        for attr in [
            'NSWorkspace', 'NSWorkspaceDidActivateApplicationNotification',
            'NSWorkspaceDidTerminateApplicationNotification',
            'NSDefaultRunLoopMode', 'NSDate', 'NSRunLoop', 'NSNotification',
        ]:
            setattr(cocoa_mod, attr, MagicMock())
        sys.modules['Cocoa'] = cocoa_mod

    # AppKit — just needs the one constant watchdog imports
    if 'AppKit' not in sys.modules:
        appkit_mod = types.ModuleType('AppKit')
        appkit_mod.NSWorkspaceDidTerminateApplicationNotification = MagicMock()
        sys.modules['AppKit'] = appkit_mod

    # objc — always replace with a plain stub so we're never touching the real
    # C extension (pyobjc >= 10 makes objc.selector an immutable C type that
    # rejects attribute assignment).
    objc_stub = MagicMock()
    objc_stub.typedSelector = lambda sig: (lambda f: f)
    objc_stub.selector = MagicMock()
    objc_stub.super = MagicMock()
    sys.modules['objc'] = objc_stub

    for name in ('termios', 'tty'):
        sys.modules.setdefault(name, MagicMock())


def _import_watchdog():
    """Import (or re-use cached) the watchdog module with Cocoa stubs in place."""
    _stub_cocoa_modules()
    if 'src.mac.watchdog' in sys.modules:
        return sys.modules['src.mac.watchdog']
    import src.mac.watchdog as wd
    return wd


def _make_watchdog(serial_mock=None, verbose=False):
    """Return a WatchDog instance with attributes set directly (bypasses Cocoa init)."""
    wd = _import_watchdog()
    wdog = object.__new__(wd.WatchDog)
    wdog.ser = serial_mock or MagicMock()
    wdog.args = argparse.Namespace(verbose=verbose, rotate=None)
    wdog.plugins = {}
    wdog.running = True
    return wdog


# ---------------------------------------------------------------------------
# Source-inspection tests (no import needed)
# ---------------------------------------------------------------------------

def test_version_print_uses_fstring():
    """VERSION must be interpolated in startup print, not embedded as a literal."""
    src = _read_source()
    match = re.search(r'print\(.*?VERSION.*?is running.*?\)', src)
    assert match, "Could not find startup print statement"
    statement = match.group(0)
    assert statement.startswith("print(f"), (
        f"Startup print must use f-string, got: {statement!r}"
    )


def test_no_dead_running_variable():
    """Dead variable 'running = [True]' must not be present."""
    src = _read_source()
    assert 'running = [True]' not in src


def test_send_app_name_return_type_is_none():
    """send_app_name_to_microcontroller must be annotated -> None, not -> str."""
    src = _read_source()
    idx = src.index('def send_app_name_to_microcontroller')
    line_end = src.index('\n', idx)
    assert '-> str' not in src[idx:line_end]


# ---------------------------------------------------------------------------
# Functional tests — heartbeat send side
# ---------------------------------------------------------------------------

class TestSendHeartbeat:

    def test_send_heartbeat_writes_hb_message(self):
        """send_heartbeat() must write 'HB\\n' to the serial port."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        # Run one iteration then stop
        wdog.running = True
        def _stop_after_one(interval):
            wdog.running = False
        with patch('time.sleep', side_effect=_stop_after_one):
            wdog.send_heartbeat()

        ser.write.assert_called_once_with(b'HB\n')

    def test_send_heartbeat_uses_heartbeat_interval(self):
        """send_heartbeat() must sleep for HEARTBEAT_INTERVAL between sends."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        sleep_calls = []
        def _record_and_stop(interval):
            sleep_calls.append(interval)
            wdog.running = False

        with patch('time.sleep', side_effect=_record_and_stop):
            wdog.send_heartbeat()

        assert sleep_calls == [wd.HEARTBEAT_INTERVAL]

    def test_send_heartbeat_sends_multiple_times(self):
        """send_heartbeat() must keep sending HB on each loop iteration."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        iteration = [0]
        def _stop_after_three(interval):
            iteration[0] += 1
            if iteration[0] >= 3:
                wdog.running = False

        with patch('time.sleep', side_effect=_stop_after_three):
            wdog.send_heartbeat()

        assert ser.write.call_count == 3
        ser.write.assert_called_with(b'HB\n')

    def test_send_heartbeat_stops_when_running_false(self):
        """Setting running=False stops the heartbeat loop without another write."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.running = False   # already stopped before the loop body runs

        with patch('time.sleep'):
            wdog.send_heartbeat()

        ser.write.assert_not_called()

    def test_send_heartbeat_handles_serial_exception(self):
        """A SerialException on write must be caught — loop must continue, not crash."""
        wd = _import_watchdog()
        # Construct an exception that is caught by watchdog's `except serial.SerialException`.
        # The watchdog module binds `serial` at import time, so we use that reference.
        serial_mod = sys.modules[wd.serial.__name__]
        if not hasattr(serial_mod, 'SerialException'):
            serial_mod.SerialException = type('SerialException', (OSError,), {})
        SerialException = serial_mod.SerialException

        ser = MagicMock()
        ser.write.side_effect = SerialException("port closed")
        wdog = _make_watchdog(ser)

        iteration = [0]
        def _stop_after_one(interval):
            iteration[0] += 1
            wdog.running = False

        with patch('time.sleep', side_effect=_stop_after_one):
            wdog.send_heartbeat()   # must not raise

        assert iteration[0] == 1   # loop ran, sleep was called


class TestSendHelloBye:

    def test_send_hello_writes_correct_message(self):
        """send_hello() must write 'HELLO:<VERSION>\\n'."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_hello()
        expected = f"HELLO:{wd.VERSION}\n".encode('ascii', 'replace')
        ser.write.assert_called_once_with(expected)

    def test_send_bye_writes_correct_message(self):
        """send_bye() must write 'BYE\\n'."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_bye()
        ser.write.assert_called_once_with(b'BYE\n')

    def test_send_hello_handles_exception(self):
        """send_hello() must not raise if serial write fails."""
        ser = MagicMock()
        ser.write.side_effect = Exception("broken pipe")
        wdog = _make_watchdog(ser)
        wdog.send_hello()   # must not raise

    def test_send_bye_handles_exception(self):
        """send_bye() must not raise if serial write fails."""
        ser = MagicMock()
        ser.write.side_effect = Exception("broken pipe")
        wdog = _make_watchdog(ser)
        wdog.send_bye()     # must not raise

    def test_hello_version_matches_module_version(self):
        """The VERSION embedded in HELLO must equal the module-level VERSION constant."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_hello()
        written = ser.write.call_args[0][0].decode()
        assert written.startswith("HELLO:")
        assert written.strip() == f"HELLO:{wd.VERSION}"


class TestHeartbeatThreadLifecycle:

    def test_heartbeat_thread_runs_and_stops(self):
        """send_heartbeat() run in a real thread stops cleanly after running=False."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        writes = []

        def _counted_write(data):
            writes.append(data)

        ser.write.side_effect = _counted_write

        # Patch time.sleep in the watchdog module so the loop doesn't actually wait
        with patch.object(wd.time, 'sleep', return_value=None):
            t = threading.Thread(target=wdog.send_heartbeat)
            t.start()
            # Give the thread a moment to run a few iterations
            time.sleep(0.05)
            wdog.running = False
            t.join(timeout=1.0)

        assert not t.is_alive(), "Heartbeat thread did not stop within 1 second"
        assert all(w == b'HB\n' for w in writes), "Unexpected payload in heartbeat writes"
        assert len(writes) > 0, "Expected at least one HB write"
