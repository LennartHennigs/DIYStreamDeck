import sys
import os
import json
from unittest.mock import patch, MagicMock
import pytest

# Add project root to sys.path so imports work during tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

import types as _types
import sys as _sys

# Inject a fake playsound module so importing the plugin doesn't fail
fake_playsound_module = _types.ModuleType('playsound')
fake_playsound_module.playsound = lambda *a, **k: None
_sys.modules['playsound'] = fake_playsound_module

# Ensure plugin directory is on sys.path so `import base_plugin` succeeds
plugins_dir = _sys.path[0] + '/src/mac/plugins'
if plugins_dir not in _sys.path:
    _sys.path.insert(0, plugins_dir)

from src.mac.plugins.sounds import SoundsPlugin


@pytest.fixture
def sounds_plugin(tmp_path):
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir(parents=True, exist_ok=True)
    (sounds_dir / "beep.mp3").write_text('')
    cfg = tmp_path / "sounds.json"
    cfg.write_text(json.dumps({"sound_path": str(sounds_dir)}))
    return SoundsPlugin(str(cfg), verbose=True)


def test_play_uses_nonblocking_playsound(sounds_plugin):
    with patch('src.mac.plugins.sounds.playsound') as mock_play:
        sounds_plugin.play('beep.mp3')
    mock_play.assert_called_once()
    assert mock_play.call_args.kwargs.get('block') is False
    assert len(sounds_plugin._sounds) == 1


def test_stop_actually_stops_live_sounds(sounds_plugin):
    """stop() must call .stop() on live sound handles (real interruption,
    not just cancelling queued futures)."""
    with patch('src.mac.plugins.sounds.playsound') as mock_play:
        sounds_plugin.play('beep.mp3')
    handle = sounds_plugin._sounds[0]
    handle.is_alive.return_value = True
    sounds_plugin.stop()
    handle.stop.assert_called_once()
    assert sounds_plugin._sounds == []


def test_stop_skips_finished_sounds(sounds_plugin):
    with patch('src.mac.plugins.sounds.playsound'):
        sounds_plugin.play('beep.mp3')
    handle = sounds_plugin._sounds[0]
    handle.is_alive.return_value = False
    sounds_plugin.stop()
    handle.stop.assert_not_called()
    assert sounds_plugin._sounds == []


def test_play_after_stop_does_not_raise(sounds_plugin):
    sounds_plugin.stop()
    with patch('src.mac.plugins.sounds.playsound'):
        sounds_plugin.play("beep.mp3")


def test_stop_can_be_called_multiple_times(sounds_plugin):
    sounds_plugin.stop()
    sounds_plugin.stop()


def test_security_exception_not_double_wrapped(sounds_plugin):
    """Path traversal error must surface as 'Invalid filename', not wrapped in 'Failed to play'."""
    with pytest.raises(Exception) as exc_info:
        sounds_plugin.play("../evil.mp3")
    msg = str(exc_info.value)
    assert "Failed to play" not in msg
    assert "Invalid" in msg


def test_security_absolute_path_not_double_wrapped(sounds_plugin):
    """Absolute path rejection must surface cleanly."""
    with pytest.raises(Exception) as exc_info:
        sounds_plugin.play("/etc/passwd")
    msg = str(exc_info.value)
    assert "Failed to play" not in msg
    assert "Invalid" in msg


def test_play_missing_file_raises(sounds_plugin):
    """A valid filename that doesn't exist should raise with 'not found'."""
    with pytest.raises(Exception, match="not found"):
        sounds_plugin.play("nonexistent.mp3")


def test_play_empty_filename_raises(sounds_plugin):
    with pytest.raises(Exception):
        sounds_plugin.play("")


def test_sounds_list_is_capped(tmp_path):
    """After many plays, the live-sound list must not exceed 11 entries (cap of 10 + 1 new)."""
    sounds_dir = tmp_path / "cap_test"
    sounds_dir.mkdir(parents=True, exist_ok=True)
    for i in range(20):
        (sounds_dir / f"sound{i}.mp3").write_text('')

    cfg = tmp_path / "cap_sounds.json"
    cfg.write_text(json.dumps({"sound_path": str(sounds_dir)}))
    plugin = SoundsPlugin(str(cfg), verbose=False)

    with patch('src.mac.plugins.sounds.playsound', side_effect=lambda *a, **k: MagicMock()):
        for i in range(20):
            plugin.play(f"sound{i}.mp3")

    assert len(plugin._sounds) <= 11, (
        f"Expected _sounds to be capped at <=11, got {len(plugin._sounds)}"
    )
