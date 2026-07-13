# DIY Streamdeck — start-at-login toggle (Mac side)
# https://github.com/LennartHennigs/DIYStreamDeck
"""Register/unregister the app as a login item via a user LaunchAgent.

A lighter variant of src/mac/service/install-service.sh: this writes a
RunAtLoad-only plist (no KeepAlive) so the app simply launches at login rather
than being kept alive as a service. Shares the same label so the two never
run in parallel. Pure functions (no rumps) — driven from the menu-bar toggle.
"""
import os
import plistlib
import subprocess
import sys

from src.mac import config_paths

LABEL = 'com.lennarthennigs.diystreamdeck'
_APP_BINARY = '/Applications/DIYStreamDeck.app/Contents/MacOS/DIYStreamDeck'


def plist_path() -> str:
    """Path to the user LaunchAgent plist."""
    return os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents',
                        f'{LABEL}.plist')


def program_path() -> str:
    """What launchd should run: the bundled app binary when frozen, else the
    repo's run-statusbar.sh (dev/source runs)."""
    if getattr(sys, 'frozen', False):
        return _APP_BINARY
    return os.path.join(config_paths.bundle_root(), 'run-statusbar.sh')


def is_enabled() -> bool:
    """True when the login-item plist is installed."""
    return os.path.exists(plist_path())


def enable() -> None:
    """Write the RunAtLoad-only plist and bootstrap it into the GUI domain."""
    path = plist_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        plistlib.dump({
            'Label': LABEL,
            'ProgramArguments': [program_path()],
            'RunAtLoad': True,
        }, f)
    # Reload if a stale agent is already registered, then bootstrap fresh.
    subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}/{LABEL}'],
                   capture_output=True)
    subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', path],
                   capture_output=True)


def disable() -> None:
    """Bootout the agent (if loaded) and remove the plist."""
    subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}/{LABEL}'],
                   capture_output=True)
    try:
        os.remove(plist_path())
    except OSError:
        pass
