# DIY Streamdeck — fetch the latest Pico firmware from GitHub (Mac side)
# https://github.com/LennartHennigs/DIYStreamDeck
"""Download the newest code.py from the GitHub repo for on-device updates.

Uses the latest release tag when one exists, else the default branch. Stdlib
only (urllib) — no extra dependencies; the bundled certifi CA is used for TLS
when available.
"""
import json
import ssl
import urllib.error
import urllib.request

OWNER = 'LennartHennigs'
REPO = 'DIYStreamDeck'
REPO_URL = f'https://github.com/{OWNER}/{REPO}'
DEFAULT_BRANCH = 'main'
CODE_PY_PATH = 'src/pi_pico/code.py'

_API_LATEST = f'https://api.github.com/repos/{OWNER}/{REPO}/releases/latest'
_RAW = f'https://raw.githubusercontent.com/{OWNER}/{REPO}/{{ref}}/{CODE_PY_PATH}'


class UpdateError(Exception):
    """Raised when the latest firmware cannot be fetched."""


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': f'{REPO}-app'})
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
            return resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raise UpdateError(f'GitHub returned HTTP {e.code} for {url}') from e
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError(f'Could not reach GitHub (offline?): {e}') from e


def latest_ref() -> str:
    """Latest release tag, or the default branch when there are no releases."""
    try:
        data = json.loads(_fetch(_API_LATEST))
    except UpdateError:
        return DEFAULT_BRANCH
    return data.get('tag_name') or DEFAULT_BRANCH


def latest_code_py() -> tuple[str, str]:
    """Return (ref, code_py_text) for the newest firmware on GitHub."""
    ref = latest_ref()
    return ref, _fetch(_RAW.format(ref=ref))
