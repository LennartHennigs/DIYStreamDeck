import sys
import os
from unittest.mock import patch

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


def test_play_and_stop(monkeypatch, tmp_path):
    # create dummy sounds directory and config file
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir(parents=True, exist_ok=True)
    dummy_sound = sounds_dir / "beep.mp3"
    dummy_sound.write_text('')

    cfg = tmp_path / "sounds.json"
    # Use absolute path so the plugin can locate the file during test
    cfg.write_text('{"sound_path": "' + str(sounds_dir) + '"}')

    # ensure playsound is available by injecting a fake into sys.modules
    # patch playsound to avoid real playback
    with patch('src.mac.plugins.sounds.playsound') as fake_playsound:
        sp = SoundsPlugin(str(cfg), verbose=True)
        sp.play('beep.mp3')
        assert len(sp._futures) == 1
        sp.stop()
        assert len(sp._futures) == 0
