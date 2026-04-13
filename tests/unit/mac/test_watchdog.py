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
    wdog._serial_lock = threading.Lock()
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


class TestSerialWriteThreadSafety:

    def test_heartbeat_routes_through_serial_write(self):
        """send_heartbeat must call _serial_write, not ser.write directly."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        serial_write_calls = []

        def recording_serial_write(self_inner, message, label):
            serial_write_calls.append((message, label))
            ser.write(message.encode('ascii', 'replace'))

        with patch.object(wd.WatchDog, '_serial_write', recording_serial_write):
            wdog.running = True
            def _stop_after_one(interval):
                wdog.running = False
            with patch('time.sleep', side_effect=_stop_after_one):
                wdog.send_heartbeat()

        assert any('HB' in call[0] for call in serial_write_calls), (
            "send_heartbeat must route through _serial_write, not call ser.write directly"
        )

    def test_serial_write_uses_lock(self):
        """_serial_write must acquire _serial_lock before writing."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        # Replace the real lock with a mock so we can observe acquire/release
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        wdog._serial_lock = mock_lock

        wdog._serial_write("TEST\n", "TEST")

        assert mock_lock.__enter__.call_count == 1, "_serial_write must acquire _serial_lock (context manager)"
        assert mock_lock.__exit__.call_count == 1, "_serial_write must release _serial_lock on exit"


class TestGetAppName:

    def test_get_app_name_returns_localized_name(self):
        """_get_app_name returns localizedName when available."""
        wdog = _make_watchdog()
        app = MagicMock()
        app.localizedName.return_value = "Spotify"
        assert wdog._get_app_name(app) == "Spotify"

    def test_get_app_name_falls_back_to_bundle_id(self):
        """_get_app_name returns bundleIdentifier when localizedName is empty."""
        wdog = _make_watchdog()
        app = MagicMock()
        app.localizedName.return_value = ""
        app.bundleIdentifier.return_value = "com.spotify.client"
        app.bundleExecutable.return_value = "Spotify"
        assert wdog._get_app_name(app) == "com.spotify.client"

    def test_get_app_name_all_none_returns_unknown(self):
        """_get_app_name must return 'unknown' when all properties are None/empty."""
        wdog = _make_watchdog()
        app = MagicMock()
        app.localizedName.return_value = None
        app.bundleIdentifier.return_value = None
        app.bundleExecutable.return_value = None
        result = wdog._get_app_name(app)
        assert result == "unknown", f"Expected 'unknown', got {result!r}"

    def test_get_app_name_returns_str_not_none(self):
        """_get_app_name must never return None."""
        wdog = _make_watchdog()
        app = MagicMock()
        app.localizedName.return_value = None
        app.bundleIdentifier.return_value = None
        app.bundleExecutable.return_value = None
        result = wdog._get_app_name(app)
        assert isinstance(result, str), f"Expected str, got {type(result)}"


class TestRunPluginCommandVerbose:

    def test_command_not_found_respects_verbose_false(self):
        """'Command not found' must NOT print when verbose=False."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser, verbose=False)

        plugin_mock = MagicMock()
        plugin_mock.commands.return_value = {}  # no matching command
        wdog.plugins = {'myplugin': plugin_mock}

        import re
        match = re.match(r'^Run: (.+)$', 'Run: myplugin.nonexistent')
        import io
        with patch('builtins.print') as mock_print:
            wdog.run_plugin_command(match)
        # With verbose=False, "Command not found" must not be printed
        for call_args in mock_print.call_args_list:
            assert 'not found' not in str(call_args).lower(), (
                f"'not found' printed with verbose=False: {call_args}"
            )

    def test_command_not_found_prints_when_verbose_true(self):
        """'Command not found' must print when verbose=True."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser, verbose=True)

        plugin_mock = MagicMock()
        plugin_mock.commands.return_value = {}
        wdog.plugins = {'myplugin': plugin_mock}

        import re
        match = re.match(r'^Run: (.+)$', 'Run: myplugin.nonexistent')
        with patch('builtins.print') as mock_print:
            wdog.run_plugin_command(match)
        printed = ' '.join(str(c) for c in mock_print.call_args_list)
        assert 'not found' in printed.lower(), (
            "Expected 'not found' to be printed with verbose=True"
        )


class TestSecurityGuards:

    def test_launch_app_rejects_path_separator(self):
        """launch_app must reject names containing '/' to prevent binary path abuse."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        for bad_name in ['/usr/bin/evil', 'App/Subdir', 'App\\Evil', 'App\x00Null', '-application']:
            mock_match = MagicMock()
            mock_match.group.return_value = bad_name
            with patch('subprocess.run') as mock_run:
                wdog.launch_app(mock_match)
                assert mock_run.call_count == 0, f"subprocess.run must not be called for unsafe name {bad_name!r}"

    def test_launch_app_allows_normal_names(self):
        """launch_app must accept normal macOS application names."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        for good_name in ['Spotify', 'Google Chrome', 'Visual Studio Code', 'zoom.us']:
            mock_match = MagicMock()
            mock_match.group.return_value = good_name
            with patch('subprocess.run') as mock_run:
                wdog.launch_app(mock_match)
                assert mock_run.call_count == 1, f"subprocess.run must be called for safe name {good_name!r}"

    def test_get_url_rejects_unknown_app(self):
        """get_url must return '' for any app not in its known-safe allowlist."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        # These names must never trigger osascript
        for unsafe_name in ['"; touch /tmp/pwned; echo "', 'Firefox', 'unknownApp']:
            with patch('subprocess.Popen') as mock_popen:
                result = wdog.get_url(unsafe_name)
                assert result == '', f"get_url must return '' for {unsafe_name!r}"
                assert mock_popen.call_count == 0, f"osascript must not run for {unsafe_name!r}"

    def test_get_url_allows_known_browsers(self):
        """get_url must invoke osascript for Google Chrome and Safari."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b'', b'')
        with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
            wdog.get_url('Google Chrome')
            assert mock_popen.call_count == 1

        with patch('subprocess.Popen', return_value=mock_proc) as mock_popen:
            wdog.get_url('Safari')
            assert mock_popen.call_count == 1


class TestLaunchApp:

    def test_launch_app_logs_failure_when_verbose(self, capsys):
        """launch_app must print a failure message when CalledProcessError occurs and verbose=True."""
        import re
        import subprocess as subproc
        wdog = _make_watchdog(verbose=True)
        m = re.match(r'Launch: (.+)', 'Launch: NonExistentApp')
        with patch('subprocess.run',
                   side_effect=subproc.CalledProcessError(1, 'open')):
            wdog.launch_app(m)
        captured = capsys.readouterr()
        # Current code already prints "Launching: ..." — this test requires an *additional*
        # failure/error indication after the CalledProcessError.
        assert any(word in captured.out.lower()
                   for word in ['fail', 'error', 'could not']), (
            "Expected a failure/error message after CalledProcessError, not just 'Launching:'"
        )

    def test_launch_app_silent_on_failure_when_not_verbose(self, capsys):
        """launch_app must not print anything on CalledProcessError when verbose=False."""
        import re
        import subprocess as subproc
        wdog = _make_watchdog(verbose=False)
        m = re.match(r'Launch: (.+)', 'Launch: NonExistentApp')
        with patch('subprocess.run',
                   side_effect=subproc.CalledProcessError(1, 'open')):
            wdog.launch_app(m)   # must not raise
        captured = capsys.readouterr()
        # No output expected when verbose is off
        assert not captured.out


class TestGetUrlAppleScriptEscaping:

    def test_get_url_escapes_app_name_before_interpolation(self):
        """app_name must be escaped before being interpolated into the AppleScript string.

        The fix introduces `safe_app_name = app_name.replace('"', '\\"')` and uses
        safe_app_name in the tell-application block (defense in depth alongside allowlist).
        """
        src = _read_source()
        assert 'safe_app_name' in src, (
            "get_url must use a 'safe_app_name' variable to hold the escaped app name"
        )
        assert 'replace' in src, (
            "get_url must call .replace() to escape double-quotes in the app name"
        )

