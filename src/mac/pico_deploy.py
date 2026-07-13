# DIY Streamdeck — push files to the Pico's CIRCUITPY drive (Mac side)
# https://github.com/LennartHennigs/DIYStreamDeck
"""Copy files (key_def.json, code.py) onto the Pico from the menu-bar app.

The Pico reads key_def.json/code.py from its own CIRCUITPY drive; CircuitPython
auto-reload restarts code.py when the host writes there, so a copy is all that's
needed to reload. Writes use a temporary noasync remount (macOS 14+ FAT32 write
safety, mirroring deploy-to-pico.sh); that remount needs root, so it runs via a
single macOS admin prompt.
"""
import os
import subprocess

from src.mac import config_paths

DEFAULT_MOUNT = '/Volumes/CIRCUITPY'


class PicoDeployError(Exception):
    """Raised when a push cannot be completed (not mounted, admin cancelled, …)."""


def circuitpy_mount(mount: str = DEFAULT_MOUNT) -> str | None:
    """Return the CIRCUITPY mount path if present and a CircuitPython drive."""
    if os.path.isdir(mount) and os.path.exists(os.path.join(mount, 'boot_out.txt')):
        return mount
    return None


def _admin_shell(script: str) -> None:
    """Run a shell snippet as root via one macOS admin-password prompt."""
    osa = f'do shell script {_as_applescript_string(script)} with administrator privileges'
    result = subprocess.run(['osascript', '-e', osa], capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or '').strip()
        if 'User canceled' in err or '-128' in err:
            raise PicoDeployError('Admin authorization cancelled')
        raise PicoDeployError(f'Deploy failed: {err or "unknown error"}')


def _as_applescript_string(text: str) -> str:
    """Quote a string as an AppleScript literal."""
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def push_file(src_path: str, dest_name: str, mount: str = DEFAULT_MOUNT) -> None:
    """Copy src_path to <mount>/<dest_name> with a FAT32-safe noasync remount."""
    if not os.path.exists(src_path):
        raise PicoDeployError(f'{src_path} not found')
    if circuitpy_mount(mount) is None:
        raise PicoDeployError('Pico storage not mounted')

    device = _mount_device(mount)
    dest = os.path.join(mount, dest_name)
    # Remount noasync, copy, sync — all as one privileged step.
    _admin_shell(
        f'umount {_sh(mount)} && '
        f'mount -o noasync -t msdos {_sh(device)} {_sh(mount)} && '
        f'cp -X {_sh(src_path)} {_sh(dest)} && sync'
    )


def push_key_def(config_dir: str | None = None, mount: str = DEFAULT_MOUNT) -> None:
    """Push the config folder's key_def.json to the Pico."""
    cfg = config_dir or config_paths.config_dir()
    push_file(os.path.join(cfg, 'key_def.json'), 'key_def.json', mount)


def _mount_device(mount: str) -> str:
    """Resolve the /dev node backing a mount point (via df)."""
    out = subprocess.run(['df', mount], capture_output=True, text=True)
    lines = out.stdout.splitlines()
    if len(lines) < 2:
        raise PicoDeployError(f'Could not resolve device for {mount}')
    return lines[1].split()[0]


def _sh(path: str) -> str:
    """Single-quote a path for the shell snippet."""
    return "'" + path.replace("'", "'\\''") + "'"
