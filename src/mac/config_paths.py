# DIY Streamdeck — user config directory resolution (Mac side)
# https://github.com/LennartHennigs/DIYStreamDeck
"""Locate and seed the user-editable config folder.

Both the packaged .app and source/dev runs resolve their key_def.json and plugin
config files from a single visible folder (default ~/Documents/DIYStreamDeck).
The bundled/repo copies are used only as first-run seed sources.

Set STREAMDECK_CONFIG_DIR to override the location (also honoured by the tests).
"""
import os
import shutil
import sys

_ENV_VAR = 'STREAMDECK_CONFIG_DIR'
_DEFAULT_DIR = os.path.join(os.path.expanduser('~'), 'Documents', 'DIYStreamDeck')


def config_dir() -> str:
    """The user config folder — env override or the default under ~/Documents."""
    return os.environ.get(_ENV_VAR) or _DEFAULT_DIR


def key_def_path() -> str:
    """Path to the user's key_def.json inside the config folder."""
    return os.path.join(config_dir(), 'key_def.json')


def bundle_root() -> str:
    """Root that contains src/… — sys._MEIPASS when frozen, else the repo root.

    Shared by statusbar.py to locate bundled assets under the same layout.
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    # src/mac/config_paths.py -> src/mac -> src -> repo root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def ensure_config_dir() -> str:
    """Create the config folder and seed defaults on first run; return its path.

    Never clobbers existing files — only copies a seed source when the
    destination is absent. key_def.json is seeded active; plugin configs are
    seeded as .json.example templates (rename to .json to activate).
    """
    target = config_dir()
    os.makedirs(target, exist_ok=True)
    root = bundle_root()

    key_def_src = os.path.join(root, 'src', 'pi_pico', 'key_def.json')
    key_def_dst = os.path.join(target, 'key_def.json')
    if os.path.exists(key_def_src) and not os.path.exists(key_def_dst):
        shutil.copy(key_def_src, key_def_dst)

    template_dir = os.path.join(root, 'src', 'mac', 'plugins_config')
    if os.path.isdir(template_dir):
        for name in os.listdir(template_dir):
            dst = os.path.join(target, name)
            if name.endswith('.json.example') and not os.path.exists(dst):
                shutil.copy(os.path.join(template_dir, name), dst)

    return target
