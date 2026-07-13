"""Tests for src/mac/config_paths.py — user config dir resolution + seeding."""
import os

import pytest

from src.mac import config_paths


def test_config_dir_default(monkeypatch):
    monkeypatch.delenv('STREAMDECK_CONFIG_DIR', raising=False)
    expected = os.path.join(os.path.expanduser('~'), 'Documents', 'DIYStreamDeck')
    assert config_paths.config_dir() == expected


def test_config_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv('STREAMDECK_CONFIG_DIR', str(tmp_path))
    assert config_paths.config_dir() == str(tmp_path)
    assert config_paths.key_def_path() == str(tmp_path / 'key_def.json')


def test_ensure_config_dir_creates_and_seeds(monkeypatch, tmp_path):
    target = tmp_path / 'DIYStreamDeck'
    monkeypatch.setenv('STREAMDECK_CONFIG_DIR', str(target))

    returned = config_paths.ensure_config_dir()

    assert returned == str(target)
    assert target.is_dir()
    # key_def.json seeded from the repo copy
    assert (target / 'key_def.json').exists()
    # plugin config templates seeded as .json.example
    examples = sorted(p.name for p in target.glob('*.json.example'))
    assert 'claude.json.example' in examples
    assert 'spotify.json.example' in examples


def test_ensure_config_dir_is_idempotent(monkeypatch, tmp_path):
    target = tmp_path / 'DIYStreamDeck'
    monkeypatch.setenv('STREAMDECK_CONFIG_DIR', str(target))

    config_paths.ensure_config_dir()
    # user edits their key_def.json — a second run must not clobber it
    (target / 'key_def.json').write_text('{"applications": {"_mine": {}}}')
    config_paths.ensure_config_dir()

    assert (target / 'key_def.json').read_text() == '{"applications": {"_mine": {}}}'
