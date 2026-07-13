"""Tests for the start-at-login helper (LaunchAgent login item)."""
import os
import plistlib
import sys
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.mac import login_item


def test_program_path_source_uses_run_statusbar(monkeypatch):
    monkeypatch.setattr(login_item.sys, 'frozen', False, raising=False)
    monkeypatch.setattr(login_item.config_paths, 'bundle_root', lambda: '/repo')
    assert login_item.program_path() == '/repo/run-statusbar.sh'


def test_program_path_frozen_uses_app_binary(monkeypatch):
    monkeypatch.setattr(login_item.sys, 'frozen', True, raising=False)
    assert login_item.program_path() == login_item._APP_BINARY


def test_enable_writes_runatload_only_plist(tmp_path, monkeypatch):
    plist = tmp_path / 'agent.plist'
    monkeypatch.setattr(login_item, 'plist_path', lambda: str(plist))
    monkeypatch.setattr(login_item, 'program_path', lambda: '/repo/run-statusbar.sh')
    calls = []
    monkeypatch.setattr(login_item.subprocess, 'run',
                        lambda *a, **k: calls.append(a[0]))

    assert not login_item.is_enabled()
    login_item.enable()

    assert login_item.is_enabled()
    with open(plist, 'rb') as f:
        data = plistlib.load(f)
    assert data['Label'] == login_item.LABEL
    assert data['ProgramArguments'] == ['/repo/run-statusbar.sh']
    assert data['RunAtLoad'] is True
    assert 'KeepAlive' not in data                       # login item, not a service
    assert any('bootstrap' in c for c in calls)          # registered with launchctl


def test_disable_removes_plist(tmp_path, monkeypatch):
    plist = tmp_path / 'agent.plist'
    plist.write_bytes(b'x')
    monkeypatch.setattr(login_item, 'plist_path', lambda: str(plist))
    monkeypatch.setattr(login_item.subprocess, 'run', mock.Mock())

    assert login_item.is_enabled()
    login_item.disable()
    assert not login_item.is_enabled()


def test_disable_is_safe_when_absent(tmp_path, monkeypatch):
    plist = tmp_path / 'missing.plist'
    monkeypatch.setattr(login_item, 'plist_path', lambda: str(plist))
    monkeypatch.setattr(login_item.subprocess, 'run', mock.Mock())
    login_item.disable()  # no exception
