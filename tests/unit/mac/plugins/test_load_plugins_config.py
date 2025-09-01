"""
Tests for plugin config selection behavior in load_plugins()
"""
import os
import json
import tempfile
import sys
import types
from importlib import import_module


def _create_dummy_plugin(path, name):
    """Create a minimal plugin file in the given path with a Plugin class."""
    content = f"""
from src.mac.plugins.base_plugin import BasePlugin

class {name.capitalize()}Plugin(BasePlugin):
    def __init__(self, config_file: str, verbose: bool) -> None:
        self.verbose = verbose
        # record which config file was passed
        self._config_file_used = config_file

    def commands(self):
        return {{}}
"""
    with open(os.path.join(path, f"{name}.py"), 'w') as f:
        f.write(content)


def test_load_plugins_prefers_central(tmp_path, monkeypatch, capsys):
    # Prepare a temporary src/mac directory structure
    project_src = tmp_path / "src" / "mac"
    plugins_dir = project_src / "plugins"
    plugins_dir.mkdir(parents=True)

    # Create dummy plugin file
    _create_dummy_plugin(str(plugins_dir), "dummy")

    # Create central plugins_config with dummy.json
    plugins_config_dir = project_src / "plugins_config"
    plugins_config_dir.mkdir()
    central_config = plugins_config_dir / "dummy.json"
    central_config.write_text(json.dumps({"foo": "bar"}))

    # Ensure the load_plugins will look into our tmp src by patching __file__
    # Ensure macOS-only modules are stubbed before importing the watchdog module
    # Create a lightweight Cocoa stub with the symbols used at import-time
    cocoa_mod = types.ModuleType("Cocoa")
    # Minimal NSObject base
    cocoa_mod.NSObject = type("NSObject", (object,), {})

    # NSRunLoop stub with required methods
    class _RunLoop:
        def runMode_beforeDate_(self, mode, date):
            return None

    class _NSDate:
        @staticmethod
        def dateWithTimeIntervalSinceNow_(t):
            return None

    cocoa_mod.NSRunLoop = type("NSRunLoop", (), {"currentRunLoop": staticmethod(lambda: _RunLoop())})
    cocoa_mod.NSDefaultRunLoopMode = "default"
    cocoa_mod.NSDate = _NSDate
    # Minimal NSNotification and NSWorkspace/notificationCenter stubs used at import-time
    cocoa_mod.NSNotification = type("NSNotification", (), {})

    class _NotificationCenter:
        def addObserver_selector_name_object_(self, *a, **k):
            return None

    class _Workspace:
        @staticmethod
        def sharedWorkspace():
            return type("WS", (), {"notificationCenter": staticmethod(lambda: _NotificationCenter())})()

    cocoa_mod.NSWorkspace = _Workspace

    sys.modules.setdefault("Cocoa", cocoa_mod)
    objc_mod = types.ModuleType("objc")
    # Provide a typedSelector decorator used in watchdog.py
    def _typedSelector(sig):
        def _decorator(f):
            return f
        return _decorator
    objc_mod.typedSelector = _typedSelector
    # Provide a simple super wrapper that delegates to builtin super
    objc_mod.super = super
    # Provide a selector factory placeholder
    objc_mod.selector = lambda func, signature=None: func
    sys.modules.setdefault("objc", objc_mod)
    # AppKit needs a specific symbol used by watchdog.py
    appkit_mod = types.ModuleType("AppKit")
    appkit_mod.NSWorkspaceDidTerminateApplicationNotification = object()
    sys.modules.setdefault("AppKit", appkit_mod)
    serial_mod = types.ModuleType("serial")
    class _DummySerial:
        def __init__(self, *a, **k):
            pass
    serial_mod.Serial = _DummySerial
    sys.modules.setdefault("serial", serial_mod)

    monkeypatch.chdir(str(tmp_path))
    sys.path.insert(0, str(project_src.parent))  # insert tmp/src on path

    watchdog_mod = import_module('src.mac.watchdog')
    # Point the module __file__ at the temporary src/mac so load_plugins resolves base_path there
    watchdog_mod.__file__ = str(project_src / 'watchdog.py')
    load_plugins = watchdog_mod.load_plugins
    plugins = load_plugins(path="plugins", verbose=True)

    # Capture stdout and assert that the central config path was printed and plugin loaded
    captured = capsys.readouterr()
    assert "Using central config for plugin 'dummy'" in captured.out
    assert 'dummy' in plugins


def test_load_plugins_fallback_to_plugin_local(tmp_path, monkeypatch, capsys):
    project_src = tmp_path / "src" / "mac"
    plugins_dir = project_src / "plugins"
    plugins_config_dir = project_src / "plugins_config"
    plugins_dir.mkdir(parents=True)
    plugins_config_dir.mkdir()

    # Create dummy plugin file
    _create_dummy_plugin(str(plugins_dir), "localonly")

    # Create plugin-local config under plugins/config/localonly.json
    plugin_local_config_dir = plugins_dir / "config"
    plugin_local_config_dir.mkdir()
    (plugin_local_config_dir / "localonly.json").write_text(json.dumps({"x": 1}))

    cocoa_mod = types.ModuleType("Cocoa")
    cocoa_mod.NSObject = type("NSObject", (object,), {})
    class _RunLoop:
        def runMode_beforeDate_(self, mode, date):
            return None
    class _NSDate:
        @staticmethod
        def dateWithTimeIntervalSinceNow_(t):
            return None
    cocoa_mod.NSRunLoop = type("NSRunLoop", (), {"currentRunLoop": staticmethod(lambda: _RunLoop())})
    cocoa_mod.NSDefaultRunLoopMode = "default"
    cocoa_mod.NSDate = _NSDate
    sys.modules.setdefault("Cocoa", cocoa_mod)
    objc_mod = types.ModuleType("objc")
    def _typedSelector(sig):
        def _decorator(f):
            return f
        return _decorator
    objc_mod.typedSelector = _typedSelector
    objc_mod.super = super
    objc_mod.selector = lambda func, signature=None: func
    sys.modules.setdefault("objc", objc_mod)
    appkit_mod = types.ModuleType("AppKit")
    appkit_mod.NSWorkspaceDidTerminateApplicationNotification = object()
    sys.modules.setdefault("AppKit", appkit_mod)
    serial_mod = types.ModuleType("serial")
    class _DummySerial:
        def __init__(self, *a, **k):
            pass
    serial_mod.Serial = _DummySerial
    sys.modules.setdefault("serial", serial_mod)

    monkeypatch.chdir(str(tmp_path))
    sys.path.insert(0, str(project_src.parent))

    watchdog_mod = import_module('src.mac.watchdog')
    watchdog_mod.__file__ = str(project_src / 'watchdog.py')
    load_plugins = watchdog_mod.load_plugins
    plugins = load_plugins(path="plugins", verbose=True)
    captured = capsys.readouterr()
    assert "Using plugin-local config for plugin 'localonly'" in captured.out
    assert 'localonly' in plugins


def test_load_plugins_skips_when_no_config(tmp_path, monkeypatch, capsys):
    project_src = tmp_path / "src" / "mac"
    plugins_dir = project_src / "plugins"
    plugins_dir.mkdir(parents=True)

    _create_dummy_plugin(str(plugins_dir), "skipped")

    cocoa_mod = types.ModuleType("Cocoa")
    cocoa_mod.NSObject = type("NSObject", (object,), {})
    class _RunLoop:
        def runMode_beforeDate_(self, mode, date):
            return None
    class _NSDate:
        @staticmethod
        def dateWithTimeIntervalSinceNow_(t):
            return None
    cocoa_mod.NSRunLoop = type("NSRunLoop", (), {"currentRunLoop": staticmethod(lambda: _RunLoop())})
    cocoa_mod.NSDefaultRunLoopMode = "default"
    cocoa_mod.NSDate = _NSDate
    sys.modules.setdefault("Cocoa", cocoa_mod)
    objc_mod = types.ModuleType("objc")
    def _typedSelector(sig):
        def _decorator(f):
            return f
        return _decorator
    objc_mod.typedSelector = _typedSelector
    objc_mod.super = super
    objc_mod.selector = lambda func, signature=None: func
    sys.modules.setdefault("objc", objc_mod)
    appkit_mod = types.ModuleType("AppKit")
    appkit_mod.NSWorkspaceDidTerminateApplicationNotification = object()
    sys.modules.setdefault("AppKit", appkit_mod)
    serial_mod = types.ModuleType("serial")
    class _DummySerial:
        def __init__(self, *a, **k):
            pass
    serial_mod.Serial = _DummySerial
    sys.modules.setdefault("serial", serial_mod)

    monkeypatch.chdir(str(tmp_path))
    sys.path.insert(0, str(project_src.parent))

    watchdog_mod = import_module('src.mac.watchdog')
    watchdog_mod.__file__ = str(project_src / 'watchdog.py')
    load_plugins = watchdog_mod.load_plugins
    plugins = load_plugins(path="plugins", verbose=True)
    captured = capsys.readouterr()

    assert "Skipping plugin 'skipped': no config found" in captured.out
    assert 'skipped' not in plugins
