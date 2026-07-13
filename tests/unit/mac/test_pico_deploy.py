"""Tests for src/mac/pico_deploy.py — CIRCUITPY mount detection + safe push."""
import os
from unittest import mock

import pytest

from src.mac import pico_deploy


def test_circuitpy_mount_detected(tmp_path):
    (tmp_path / 'boot_out.txt').write_text('Adafruit CircuitPython')
    assert pico_deploy.circuitpy_mount(str(tmp_path)) == str(tmp_path)


def test_circuitpy_mount_missing(tmp_path):
    # directory without boot_out.txt is not a CircuitPython drive
    assert pico_deploy.circuitpy_mount(str(tmp_path)) is None
    assert pico_deploy.circuitpy_mount('/no/such/mount') is None


def test_sh_quotes_single_quotes():
    assert pico_deploy._sh("a'b") == "'a'\\''b'"


def test_mount_device_parses_df():
    fake = mock.Mock(stdout="Filesystem ...\n/dev/disk4s1  ... /Volumes/CIRCUITPY\n")
    with mock.patch('src.mac.pico_deploy.subprocess.run', return_value=fake):
        assert pico_deploy._mount_device('/Volumes/CIRCUITPY') == '/dev/disk4s1'


def test_push_file_raises_when_source_missing(tmp_path):
    with pytest.raises(pico_deploy.PicoDeployError, match='not found'):
        pico_deploy.push_file(str(tmp_path / 'nope.json'), 'key_def.json', str(tmp_path))


def test_push_file_raises_when_not_mounted(tmp_path):
    src = tmp_path / 'key_def.json'
    src.write_text('{}')
    # tmp_path has no boot_out.txt -> not a CircuitPython mount
    with pytest.raises(pico_deploy.PicoDeployError, match='not mounted'):
        pico_deploy.push_file(str(src), 'key_def.json', str(tmp_path))


def test_push_file_runs_privileged_copy(tmp_path):
    mount = tmp_path / 'CIRCUITPY'
    mount.mkdir()
    (mount / 'boot_out.txt').write_text('cp')
    src = tmp_path / 'key_def.json'
    src.write_text('{}')

    with mock.patch('src.mac.pico_deploy._mount_device', return_value='/dev/disk9s1'), \
         mock.patch('src.mac.pico_deploy._admin_shell') as admin:
        pico_deploy.push_file(str(src), 'key_def.json', str(mount))

    admin.assert_called_once()
    script = admin.call_args[0][0]
    assert 'mount -o noasync -t msdos' in script
    assert '/dev/disk9s1' in script
    assert 'sync' in script


def test_admin_shell_reports_cancel():
    fake = mock.Mock(returncode=1, stderr='User canceled.')
    with mock.patch('src.mac.pico_deploy.subprocess.run', return_value=fake):
        with pytest.raises(pico_deploy.PicoDeployError, match='cancel'):
            pico_deploy._admin_shell('true')
