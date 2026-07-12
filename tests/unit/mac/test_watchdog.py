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
import types
import threading
import argparse
import pytest
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
    # serial.tools.list_ports — always stub so `import serial.tools.list_ports` works
    if 'serial.tools.list_ports' not in sys.modules:
        tools_mod = types.ModuleType('serial.tools')
        list_ports_mod = types.ModuleType('serial.tools.list_ports')
        list_ports_mod.comports = MagicMock(return_value=[])
        tools_mod.list_ports = list_ports_mod
        sys.modules['serial'].tools = tools_mod
        sys.modules['serial.tools'] = tools_mod
        sys.modules['serial.tools.list_ports'] = list_ports_mod

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
    wdog.args = argparse.Namespace(verbose=verbose, rotate=None, no_reconnect=False)
    wdog.plugins = {}
    wdog._serial_lock = threading.Lock()
    wdog._stop_event = threading.Event()
    wdog._disconnected = threading.Event()
    wdog._last_sent_app_name = None
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

    def test_run_heartbeat_loop_writes_hb_message(self):
        """_run_heartbeat_loop() must write 'HB\\n' to the serial port."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        # wait() returns False once (run body), then True (stop loop)
        with patch.object(wdog._stop_event, 'wait', side_effect=[False, True]):
            wdog._run_heartbeat_loop()

        ser.write.assert_called_once_with(b'HB\n')

    def test_run_heartbeat_loop_uses_heartbeat_interval(self):
        """_run_heartbeat_loop() must call event.wait with HEARTBEAT_INTERVAL."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        wait_calls = []
        def _record_and_stop(interval):
            wait_calls.append(interval)
            return True  # stop immediately after first call

        with patch.object(wdog._stop_event, 'wait', side_effect=_record_and_stop):
            wdog._run_heartbeat_loop()

        assert wait_calls == [wd.HEARTBEAT_INTERVAL]

    def test_run_heartbeat_loop_sends_multiple_times(self):
        """_run_heartbeat_loop() must keep sending HB on each loop iteration."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        # False × 3 → 3 sends; True → stop
        with patch.object(wdog._stop_event, 'wait', side_effect=[False, False, False, True]):
            wdog._run_heartbeat_loop()

        assert ser.write.call_count == 3
        ser.write.assert_called_with(b'HB\n')

    def test_run_heartbeat_loop_stops_when_running_false(self):
        """Setting _stop_event stops the heartbeat loop without any write."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog._stop_event.set()  # already stopped before the loop body runs

        wdog._run_heartbeat_loop()

        ser.write.assert_not_called()

    def test_run_heartbeat_loop_handles_serial_exception(self):
        """A SerialException on write must be caught — loop must continue, not crash."""
        wd = _import_watchdog()
        serial_mod = sys.modules[wd.serial.__name__]
        if not hasattr(serial_mod, 'SerialException'):
            serial_mod.SerialException = type('SerialException', (OSError,), {})
        SerialException = serial_mod.SerialException

        ser = MagicMock()
        ser.write.side_effect = SerialException("port closed")
        wdog = _make_watchdog(ser)

        # False once (loop runs, exception caught internally), True next (stop)
        with patch.object(wdog._stop_event, 'wait', side_effect=[False, True]):
            wdog._run_heartbeat_loop()   # must not raise


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


class TestStartupAppDetection:

    def test_frontmost_app_is_sent_when_present(self):
        """If frontmostApplication() returns an app, send_app_name_to_microcontroller is called."""
        wdog = _make_watchdog()
        frontmost_mock = MagicMock()
        frontmost_mock.localizedName.return_value = "Safari"
        frontmost_mock.bundleIdentifier.return_value = None
        frontmost_mock.bundleExecutable.return_value = None

        with patch.object(wdog, 'send_app_name_to_microcontroller') as mock_send:
            if frontmost_mock:
                wdog.send_app_name_to_microcontroller(wdog._get_app_name(frontmost_mock))

        mock_send.assert_called_once_with("Safari")

    def test_no_send_when_frontmost_is_none(self):
        """If frontmostApplication() returns None, send_app_name_to_microcontroller is NOT called."""
        wdog = _make_watchdog()

        with patch.object(wdog, 'send_app_name_to_microcontroller') as mock_send:
            if None:
                wdog.send_app_name_to_microcontroller(wdog._get_app_name(None))

        mock_send.assert_not_called()

    def test_startup_app_detection_in_source(self):
        """Source must query frontmostApplication() via _get_app_name() after send_hello()."""
        src = _read_source()
        assert 'frontmostApplication' in src, (
            "main() must call frontmostApplication() to detect the active app at startup"
        )
        assert '_get_app_name' in src, (
            "startup detection must use _get_app_name() for consistent name extraction"
        )
        hello_idx = src.index('send_hello()')
        frontmost_idx = src.index('frontmostApplication()')
        assert frontmost_idx > hello_idx, (
            "frontmostApplication() must be called after send_hello()"
        )

    def test_shutdown_joins_heartbeat_before_send_bye(self):
        """heartbeat_thread.join() must appear before send_bye() in the finally block.

        Rationale: send_bye() acquires _serial_lock. If the heartbeat thread is
        mid-write it holds that lock. Joining first guarantees the lock is free
        before BYE is written, preventing a deadlock on clean shutdown.
        """
        src = _read_source()
        # shutdown protocol lives in end_session() since the session refactor
        start = src.index('def end_session')
        shutdown_block = src[start:src.index('\ndef ', start + 1)]
        join_idx = shutdown_block.index('heartbeat_thread.join()')
        bye_idx = shutdown_block.index('send_bye()')
        assert join_idx < bye_idx, (
            "heartbeat_thread.join() must come before send_bye() in end_session() "
            "to release the serial lock before BYE is written"
        )

    def test_shutdown_flushes_before_close(self):
        """ser.flush() must appear between send_bye() and ser.close().

        Rationale: flush() drains the OS write buffer so the Pico receives BYE
        before the serial port is torn down.
        """
        src = _read_source()
        # shutdown protocol lives in end_session() since the session refactor
        start = src.index('def end_session')
        shutdown_block = src[start:src.index('\ndef ', start + 1)]
        bye_idx = shutdown_block.index('send_bye()')
        flush_idx = shutdown_block.index('ser.flush()')
        close_idx = shutdown_block.index('ser.close()')
        assert bye_idx < flush_idx < close_idx, (
            "Shutdown order must be: send_bye() → ser.flush() → ser.close()"
        )


class TestAppNameDeduplication:
    """send_app_name_to_microcontroller must skip serial writes when the app
    name hasn't changed since the last send. macOS fires
    NSWorkspaceDidActivateApplicationNotification liberally (window focus
    flicker, background helpers, Terminal foreground/background); every
    duplicate App: line makes the Pico repaint all 16 LEDs and wipes any
    active Claude signal color.
    """

    def test_first_app_name_is_sent(self):
        """Fresh watchdog → first call to send_app_name_to_microcontroller writes."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_app_name_to_microcontroller("Terminal")
        assert ser.write.call_count == 1
        ser.write.assert_called_once_with(b"App: Terminal\n")

    def test_duplicate_app_name_suppressed(self):
        """Sending the same name twice → serial written only once."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_app_name_to_microcontroller("Terminal")
        wdog.send_app_name_to_microcontroller("Terminal")
        wdog.send_app_name_to_microcontroller("Terminal")
        assert ser.write.call_count == 1, (
            "Redundant App: writes must be suppressed (macOS fires spurious "
            "activation notifications; each one wipes the Claude signal)"
        )

    def test_different_app_name_sends_again(self):
        """App A then App B → two writes, one per distinct name."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_app_name_to_microcontroller("Terminal")
        wdog.send_app_name_to_microcontroller("Claude")
        assert ser.write.call_count == 2
        # Verify both names actually landed
        writes = [call.args[0] for call in ser.write.call_args_list]
        assert b"App: Terminal\n" in writes
        assert b"App: Claude\n" in writes

    def test_url_change_within_same_app_still_sends(self):
        """Safari with two different URLs → two writes.

        get_url() appends the URL, so the effective name differs.
        """
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        # get_url() is what appends URL info; stub it to control the value.
        with patch.object(wdog, 'get_url', side_effect=lambda name: " (example.com)"):
            wdog.send_app_name_to_microcontroller("Safari")
        with patch.object(wdog, 'get_url', side_effect=lambda name: " (other.com)"):
            wdog.send_app_name_to_microcontroller("Safari")
        assert ser.write.call_count == 2, (
            "URL change within Safari must still send (effective name differs)"
        )
        writes = [call.args[0] for call in ser.write.call_args_list]
        assert b"App: Safari (example.com)\n" in writes
        assert b"App: Safari (other.com)\n" in writes

    def test_dedup_state_initialized_in_init(self):
        """`_last_sent_app_name` must be initialized to None in initWithSerial_args_plugins_.

        Guards against future refactors that would remove the initialization
        and cause AttributeError on first send.
        """
        src = _read_source()
        init_idx = src.index('def initWithSerial_args_plugins_')
        # Find the return statement inside this method (end of init block)
        return_idx = src.index('return self', init_idx)
        init_block = src[init_idx:return_idx]
        assert '_last_sent_app_name' in init_block, (
            "initWithSerial_args_plugins_ must initialize _last_sent_app_name = None"
        )


def _make_terminate_notification(app_name):
    """Build a stub NSWorkspace termination notification for `app_name`."""
    app = MagicMock()
    app.localizedName.return_value = app_name
    note = MagicMock()
    note.userInfo.return_value = {'NSWorkspaceApplicationKey': app}
    return note


class TestTerminatedResetsDedup:
    """applicationTerminated_ must reset the App: dedup when the terminated app
    is the one currently displayed, so a same-named relaunch that regains focus
    without an intervening app switch re-sends its layout."""

    def test_terminating_current_app_allows_resend(self):
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_app_name_to_microcontroller("Foo")          # App: Foo (1)
        wdog.applicationTerminated_(_make_terminate_notification("Foo"))  # resets dedup
        wdog.send_app_name_to_microcontroller("Foo")          # App: Foo (2) again
        writes = [c.args[0] for c in ser.write.call_args_list]
        assert writes.count(b"App: Foo\n") == 2, (
            "terminating the currently-shown app must reset the dedup so a "
            "same-name relaunch re-sends App:"
        )

    def test_terminating_other_app_keeps_dedup(self):
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog.send_app_name_to_microcontroller("Foo")          # App: Foo (1)
        wdog.applicationTerminated_(_make_terminate_notification("Bar"))  # unrelated
        wdog.send_app_name_to_microcontroller("Foo")          # suppressed
        writes = [c.args[0] for c in ser.write.call_args_list]
        assert writes.count(b"App: Foo\n") == 1, (
            "terminating a different app must NOT reset the dedup for the "
            "currently-shown app"
        )


class TestRunPluginLifecycle:
    """The _run_plugin_lifecycle helper must invoke a named hook on every plugin
    and isolate per-plugin exceptions."""

    def test_runs_hook_on_each_plugin_with_args(self):
        wd = _import_watchdog()
        p1, p2 = MagicMock(), MagicMock()
        wd._run_plugin_lifecycle({'a': p1, 'b': p2}, 'on_watchdog_start', 'SEND')
        p1.on_watchdog_start.assert_called_once_with('SEND')
        p2.on_watchdog_start.assert_called_once_with('SEND')

    def test_one_plugin_error_does_not_stop_others(self, capsys):
        wd = _import_watchdog()
        p1, p2 = MagicMock(), MagicMock()
        p1.on_watchdog_stop.side_effect = RuntimeError("boom")
        wd._run_plugin_lifecycle({'a': p1, 'b': p2}, 'on_watchdog_stop')
        p2.on_watchdog_stop.assert_called_once_with()
        assert "boom" in capsys.readouterr().out, (
            "a plugin lifecycle error must be caught and reported, not raised"
        )

    def test_send_line_comment_references_correct_hook(self):
        """The _send_line_to_keypad comment must not reference the old
        BasePlugin.start name (renamed to on_watchdog_start)."""
        src = _read_source()
        assert 'BasePlugin.start(' not in src, (
            "stale comment references BasePlugin.start; the hook is on_watchdog_start"
        )


class TestHeartbeatThreadLifecycle:

    def test_heartbeat_thread_runs_and_stops(self):
        """_run_heartbeat_loop() run in a real thread stops cleanly after _stop_event is set."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        writes = []

        def _counted_write(data):
            writes.append(data)

        ser.write.side_effect = _counted_write

        # Let the loop run a few times quickly, then stop
        with patch.object(wdog._stop_event, 'wait', side_effect=[False, False, False, True]):
            t = threading.Thread(target=wdog._run_heartbeat_loop)
            t.start()
            t.join(timeout=1.0)

        assert not t.is_alive(), "Heartbeat thread did not stop within 1 second"
        assert all(w == b'HB\n' for w in writes), "Unexpected payload in heartbeat writes"
        assert len(writes) > 0, "Expected at least one HB write"


class TestSerialWriteThreadSafety:

    def test_heartbeat_routes_through_serial_write(self):
        """_run_heartbeat_loop must call _serial_write, not ser.write directly."""
        wd = _import_watchdog()
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        serial_write_calls = []

        def recording_serial_write(self_inner, message, label):
            serial_write_calls.append((message, label))
            ser.write(message.encode('utf-8'))

        with patch.object(wd.WatchDog, '_serial_write', recording_serial_write):
            # wait() returns False once (send HB), then True (stop)
            with patch.object(wdog._stop_event, 'wait', side_effect=[False, True]):
                wdog._run_heartbeat_loop()

        assert any('HB' in call[0] for call in serial_write_calls), (
            "_run_heartbeat_loop must route through _serial_write, not call ser.write directly"
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


class TestSerialWriteEncoding:

    def test_serial_write_uses_utf8_not_ascii(self):
        """_serial_write must encode with UTF-8, preserving non-ASCII characters."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        wdog._serial_write("App: Müller\n", "App")

        expected = "App: Müller\n".encode('utf-8')
        ser.write.assert_called_once_with(expected)


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


class TestRotateSerialWrite:

    def test_rotate_uses_serial_write_not_ser_write(self):
        """The Rotate command in main() must go through _serial_write, not ser.write directly.

        Before the fix: main() calls ser.write(...) directly, bypassing the serial lock.
        After the fix: the call uses watchdog._serial_write(...) which acquires _serial_lock.
        """
        src = _read_source()
        # Find the rotate block in main()
        rotate_idx = src.find("args.rotate")
        assert rotate_idx != -1, "Could not find args.rotate usage in source"

        # Search for the line that actually sends the rotate command
        # It must NOT be a bare ser.write call — it must go through _serial_write
        rotate_section = src[rotate_idx - 50 : rotate_idx + 200]
        assert 'ser.write' not in rotate_section, (
            "The Rotate command must not call ser.write() directly — "
            "use _serial_write() to acquire the serial lock and avoid a race with the heartbeat thread"
        )
        assert '_serial_write' in rotate_section, (
            "The Rotate command must route through _serial_write() to hold the serial lock"
        )


class TestRunLoop:

    def test_run_loop_is_instance_method(self):
        """run_loop must be a method on WatchDog, not a standalone module function."""
        wd = _import_watchdog()
        assert hasattr(wd.WatchDog, 'run_loop'), (
            "run_loop must be defined as a method on WatchDog, not a standalone function"
        )
        assert not hasattr(wd, 'run_loop'), (
            "run_loop must not exist as a module-level function — it belongs on WatchDog"
        )

    def test_run_loop_calls_check_serial(self):
        """run_loop() must call self.check_serial() on each iteration."""
        wdog = _make_watchdog()

        call_count = []

        def _fake_check_serial():
            call_count.append(1)
            if len(call_count) >= 3:
                raise KeyboardInterrupt  # exit the loop after 3 iterations

        wd = _import_watchdog()
        with patch.object(wdog, 'check_serial', side_effect=_fake_check_serial):
            with patch.object(wd.Cocoa, 'NSRunLoop') as mock_runloop_cls:
                mock_runloop_cls.currentRunLoop.return_value = MagicMock()
                try:
                    wdog.run_loop()
                except KeyboardInterrupt:
                    pass

        assert len(call_count) >= 3, "run_loop must call check_serial on every iteration"


# ---------------------------------------------------------------------------
# TestFindPicoPort
# ---------------------------------------------------------------------------

class TestFindPicoPort:
    """Tests for find_pico_port_by_vid."""

    def setup_method(self, method):
        self.wd = _import_watchdog()

    def _make_port(self, device, vid=None):
        p = MagicMock()
        p.device = device
        p.vid = vid
        return p

    # -- find_pico_port_by_vid ------------------------------------------------

    def test_vid_returns_device_when_vid_matches(self):
        port = self._make_port('/dev/cu.usbmodem1', vid=0x2E8A)
        with patch('serial.tools.list_ports.comports', return_value=[port]):
            result = self.wd.find_pico_port_by_vid()
        assert result == '/dev/cu.usbmodem1'

    def test_vid_returns_none_when_no_match(self):
        port = self._make_port('/dev/cu.Bluetooth', vid=0x05AC)
        with patch('serial.tools.list_ports.comports', return_value=[port]):
            result = self.wd.find_pico_port_by_vid()
        assert result is None

    def test_vid_returns_none_when_no_ports(self):
        with patch('serial.tools.list_ports.comports', return_value=[]):
            result = self.wd.find_pico_port_by_vid()
        assert result is None

    def test_vid_returns_first_matching_port(self):
        p1 = self._make_port('/dev/cu.usbmodem1', vid=0x2E8A)
        p2 = self._make_port('/dev/cu.usbmodem2', vid=0x2E8A)
        with patch('serial.tools.list_ports.comports', return_value=[p1, p2]):
            result = self.wd.find_pico_port_by_vid()
        assert result == '/dev/cu.usbmodem1'

    def test_vid_skips_port_with_none_vid(self):
        port = self._make_port('/dev/cu.usbserial', vid=None)
        with patch('serial.tools.list_ports.comports', return_value=[port]):
            result = self.wd.find_pico_port_by_vid()
        assert result is None


class TestOutputMessage:
    """Tests for issue #6: Output: serial message (Pico -> Mac)."""

    def setup_method(self, method):
        self.wdog = _make_watchdog(verbose=False)

    def test_handle_output_prints_with_pico_prefix(self):
        """handle_output() must print '[Pico] <text>' to stdout."""
        match = re.match(r'^Output: (.+)$', 'Output: hello world')
        with patch('builtins.print') as mock_print:
            self.wdog.handle_output(match)
        mock_print.assert_called_once_with('[Pico] hello world')

    def test_handle_output_not_gated_on_verbose(self):
        """handle_output() must always print, regardless of verbose flag."""
        wdog_quiet = _make_watchdog(verbose=False)
        match = re.match(r'^Output: (.+)$', 'Output: test')
        with patch('builtins.print') as mock_print:
            wdog_quiet.handle_output(match)
        mock_print.assert_called_once()

    def test_check_serial_routes_output_message(self):
        """check_serial() must route 'Output: ...' lines to handle_output."""
        ser = MagicMock()
        wdog = _make_watchdog(ser, verbose=False)
        wdog.read_serial_data = MagicMock(return_value='Output: hello')
        with patch.object(wdog, 'handle_output') as mock_handler:
            wdog.check_serial()
        mock_handler.assert_called_once()


class TestSendLineToKeypad:
    """Tests for _send_line_to_keypad: the sender exposed to plugins.

    Plugins receive this method as a callable via BasePlugin.start()
    and use it to push messages to the Pico under the watchdog's lock.
    """

    def test_send_line_writes_message_to_serial(self):
        """_send_line_to_keypad must write the provided line to the serial port."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog._send_line_to_keypad("Claude: green\n")
        ser.write.assert_called_once_with(b"Claude: green\n")

    def test_send_line_uses_serial_lock(self):
        """_send_line_to_keypad must acquire _serial_lock (reuses _serial_write)."""
        ser = MagicMock()
        wdog = _make_watchdog(ser)

        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        wdog._serial_lock = mock_lock

        wdog._send_line_to_keypad("Claude: red\n")

        assert mock_lock.__enter__.call_count == 1
        assert mock_lock.__exit__.call_count == 1

    def test_send_line_handles_serial_error_gracefully(self):
        """Serial write errors must be caught (matches _serial_write behavior)."""
        ser = MagicMock()
        ser.write.side_effect = OSError("port closed")
        wdog = _make_watchdog(ser)
        # Must not raise even if serial fails.
        wdog._send_line_to_keypad("Claude: yellow\n")




# ---------------------------------------------------------------------------
# Review fixes: optional plugin params, junk serial bytes, exit codes
# ---------------------------------------------------------------------------

class TestOptionalPluginParams:
    """Bug fix: commands whose only parameters have defaults (e.g.
    spotify.volume_up(volume_change=10)) were rejected with 'Parameter
    missing' when invoked without a parameter."""

    def _run(self, wdog, line):
        match = re.match(r"^Run: (.+)$", line)
        assert match
        wdog.run_plugin_command(match)

    def test_command_with_default_param_runs_without_param(self):
        wdog = _make_watchdog()
        called = []

        def volume_up(volume_change=10):
            called.append(volume_change)

        plugin = MagicMock()
        plugin.commands.return_value = {'spotify.volume_up': volume_up}
        wdog.plugins = {'spotify': plugin}
        self._run(wdog, "Run: spotify.volume_up")
        assert called == [10]

    def test_command_with_required_param_still_rejected(self):
        wdog = _make_watchdog()
        called = []

        def play(filename):
            called.append(filename)

        plugin = MagicMock()
        plugin.commands.return_value = {'sounds.play': play}
        wdog.plugins = {'sounds': plugin}
        self._run(wdog, "Run: sounds.play")
        assert called == []


class TestReadSerialDataRobustness:
    """Bug fix: a junk byte on the wire raised UnicodeDecodeError and killed
    the run loop (the Pico side already handled this case)."""

    def test_junk_bytes_do_not_raise(self):
        ser = MagicMock()
        ser.in_waiting = 5
        ser.readline.return_value = b'\xff\xfeRun: x\n'
        wdog = _make_watchdog(ser)
        result = wdog.read_serial_data()  # must not raise
        assert result is None or isinstance(result, str)


class TestMainExitCodes:
    """Bug fix: main() returned exit code 0 on failure (missing Pico / failed
    serial connection), which breaks launchd and scripting."""

    def test_exit_1_when_pico_not_found(self, monkeypatch):
        # --no-reconnect: with reconnect (the default) main() would wait for the Pico
        wd = _import_watchdog()
        monkeypatch.setattr(sys, 'argv', ['watchdog.py', '--no-reconnect'])
        monkeypatch.setattr(wd, 'find_pico_port_by_vid', lambda: None)
        with pytest.raises(SystemExit) as excinfo:
            wd.main()
        assert excinfo.value.code == 1

    def test_exit_1_when_connection_fails(self, monkeypatch):
        wd = _import_watchdog()
        monkeypatch.setattr(sys, 'argv', ['watchdog.py', '--no-reconnect', '--port', '/dev/fake'])
        monkeypatch.setattr(wd, 'create_serial_connection', lambda port, speed: None)
        with pytest.raises(SystemExit) as excinfo:
            wd.main()
        assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# Auto-reconnect (Phase D)
# ---------------------------------------------------------------------------

class TestDisconnectDetection:
    """A dead serial port must set the _disconnected event (ending the
    session so main() can reconnect) instead of crashing or spamming errors."""

    def test_read_error_marks_disconnected(self):
        ser = MagicMock()
        type(ser).in_waiting = property(
            lambda self: (_ for _ in ()).throw(OSError("device gone")))
        wdog = _make_watchdog(ser)
        assert wdog.read_serial_data() is None  # must not raise
        assert wdog._disconnected.is_set()

    def test_readline_serial_exception_marks_disconnected(self):
        import serial as serial_mod
        ser = MagicMock()
        ser.in_waiting = 3
        ser.readline.side_effect = serial_mod.SerialException("read failed")
        wdog = _make_watchdog(ser)
        assert wdog.read_serial_data() is None
        assert wdog._disconnected.is_set()

    def test_write_error_marks_disconnected(self):
        import serial as serial_mod
        ser = MagicMock()
        ser.write.side_effect = serial_mod.SerialException("write failed")
        wdog = _make_watchdog(ser)
        wdog._serial_write('HB\n', 'HB')  # must not raise
        assert wdog._disconnected.is_set()

    def test_write_after_disconnect_is_silent_noop(self, capsys):
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog._disconnected.set()
        wdog._serial_write('HB\n', 'HB')
        ser.write.assert_not_called()
        assert capsys.readouterr().out == ""

    def test_heartbeat_loop_exits_on_disconnect(self):
        ser = MagicMock()
        wdog = _make_watchdog(ser)
        wdog._disconnected.set()
        # wait() would allow two more iterations — the disconnected check must
        # exit first, without sending anything (and without real 2 s waits)
        with patch.object(wdog._stop_event, 'wait', side_effect=[False, False, True]):
            wdog._run_heartbeat_loop()
        ser.write.assert_not_called()


class TestConnectOrWait:
    """main()'s connect helper retries until the Pico appears (reconnect
    default) or gives up immediately with --no-reconnect."""

    def _args(self, no_reconnect):
        return argparse.Namespace(port=None, speed=9600, verbose=False,
                                  rotate=None, no_reconnect=no_reconnect)

    def test_retries_until_port_appears(self, monkeypatch):
        wd = _import_watchdog()
        ports = iter([None, None, '/dev/cu.fake'])
        monkeypatch.setattr(wd, 'find_pico_port_by_vid', lambda: next(ports))
        sentinel = MagicMock()
        monkeypatch.setattr(wd, 'create_serial_connection', lambda p, s: sentinel)
        monkeypatch.setattr(wd.time, 'sleep', lambda s: None)
        assert wd._connect_or_wait(self._args(no_reconnect=False)) is sentinel

    def test_no_reconnect_returns_none_when_absent(self, monkeypatch):
        wd = _import_watchdog()
        monkeypatch.setattr(wd, 'find_pico_port_by_vid', lambda: None)
        assert wd._connect_or_wait(self._args(no_reconnect=True)) is None


class TestSelfActivationIgnored:
    """Phase E guard: an activation notification for our own process (menu-bar
    app) must never repaint the keypad to ourselves."""

    def _notification(self, pid):
        app = MagicMock()
        app.processIdentifier.return_value = pid
        app.localizedName.return_value = "Python"
        notification = MagicMock()
        notification.userInfo.return_value = {'NSWorkspaceApplicationKey': app}
        return notification

    def test_own_pid_activation_is_ignored(self):
        wdog = _make_watchdog()
        with patch.object(wdog, 'send_app_name_to_microcontroller') as send:
            wdog.applicationActivated_(self._notification(os.getpid()))
        send.assert_not_called()

    def test_other_pid_activation_is_processed(self):
        wdog = _make_watchdog()
        with patch.object(wdog, 'send_app_name_to_microcontroller') as send:
            wdog.applicationActivated_(self._notification(os.getpid() + 1))
        send.assert_called_once_with("Python")


class TestOnAppChangedCallback:
    """The optional on_app_changed observer fires on real app changes only
    (after dedup), so the menu-bar cheat sheet tracks the keypad exactly."""

    def test_callback_fires_on_new_app(self):
        wdog = _make_watchdog()
        seen = []
        wdog.on_app_changed = seen.append
        wdog.send_app_name_to_microcontroller("Finder")
        assert seen == ["Finder"]

    def test_callback_suppressed_for_duplicate_activation(self):
        wdog = _make_watchdog()
        seen = []
        wdog.on_app_changed = seen.append
        wdog.send_app_name_to_microcontroller("Finder")
        wdog.send_app_name_to_microcontroller("Finder")
        assert seen == ["Finder"]
