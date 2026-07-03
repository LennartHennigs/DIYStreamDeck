"""Tests for install-claude-hooks.sh / uninstall-claude-hooks.sh.

Verify:
- Backup file is created before mutation.
- Three hook entries land under Stop / Notification / StopFailure.
- Re-running is idempotent (no duplicate entries).
- Uninstaller removes only streamdeck-claude entries; peon-ping and
  unrelated entries are preserved.
- Invalid JSON is refused (doesn't clobber the file).
- Missing settings file is created fresh.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
INSTALL_SH = REPO_ROOT / "src" / "mac" / "hooks" / "install-claude-hooks.sh"
UNINSTALL_SH = REPO_ROOT / "src" / "mac" / "hooks" / "uninstall-claude-hooks.sh"
HOOK_SCRIPT = REPO_ROOT / "src" / "mac" / "hooks" / "streamdeck-claude.py"


def _has_jq():
    return shutil.which("jq") is not None


pytestmark = pytest.mark.skipif(not _has_jq(), reason="jq not installed")


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Point HOME at a temp dir so we don't touch the user's real settings.json."""
    home = tmp_path / "fake_home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _run(script: Path, home: Path):
    """Run an install/uninstall script with HOME overridden. Return CompletedProcess."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def _read_settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text())


def _count_streamdeck_entries(settings: dict) -> int:
    total = 0
    for event in ("Stop", "Notification", "StopFailure"):
        for entry in settings.get("hooks", {}).get(event, []):
            for h in entry.get("hooks", []):
                if str(HOOK_SCRIPT) in h.get("command", ""):
                    total += 1
    return total


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def test_install_creates_settings_when_missing(fake_home):
    """Fresh HOME with no ~/.claude directory → installer creates everything."""
    result = _run(INSTALL_SH, fake_home)
    assert result.returncode == 0, result.stderr
    assert (fake_home / ".claude" / "settings.json").exists()


def test_install_adds_three_entries(fake_home):
    _run(INSTALL_SH, fake_home)
    settings = _read_settings(fake_home)
    assert _count_streamdeck_entries(settings) == 3


def test_install_registers_correct_events(fake_home):
    _run(INSTALL_SH, fake_home)
    settings = _read_settings(fake_home)
    hooks = settings["hooks"]
    for event in ("Stop", "Notification", "StopFailure"):
        assert event in hooks, f"missing {event}"
        commands = [h["command"] for entry in hooks[event] for h in entry["hooks"]]
        assert any(str(HOOK_SCRIPT) in c for c in commands), (
            f"{event}: expected an entry pointing at {HOOK_SCRIPT}, got {commands!r}"
        )


def test_install_creates_backup(fake_home):
    # Seed with an existing settings.json so backup has something to preserve.
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"marker": "original"}')
    _run(INSTALL_SH, fake_home)
    backup = claude_dir / "settings.json.bak"
    assert backup.exists()
    assert json.loads(backup.read_text()) == {"marker": "original"}


def test_install_is_idempotent(fake_home):
    """Running installer twice must not add duplicate entries."""
    _run(INSTALL_SH, fake_home)
    settings1 = _read_settings(fake_home)
    assert _count_streamdeck_entries(settings1) == 3

    _run(INSTALL_SH, fake_home)
    settings2 = _read_settings(fake_home)
    assert _count_streamdeck_entries(settings2) == 3, (
        "second run must not duplicate entries"
    )


def test_install_preserves_existing_hooks(fake_home):
    """Existing peon-ping (or similar) entries must survive install."""
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir()
    existing = {
        "hooks": {
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": "/path/to/peon-ping.sh", "timeout": 10}
                    ],
                }
            ],
            "Notification": [
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "/other.sh"}],
                }
            ],
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(existing))

    _run(INSTALL_SH, fake_home)
    settings = _read_settings(fake_home)

    # streamdeck entries added
    assert _count_streamdeck_entries(settings) == 3
    # peon-ping still there
    stop_cmds = [h["command"] for entry in settings["hooks"]["Stop"] for h in entry["hooks"]]
    assert "/path/to/peon-ping.sh" in stop_cmds
    # /other.sh still there
    notif_cmds = [h["command"] for entry in settings["hooks"]["Notification"] for h in entry["hooks"]]
    assert "/other.sh" in notif_cmds


def test_install_refuses_invalid_json(fake_home):
    """Malformed settings.json must halt the installer, not overwrite."""
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    settings_file.write_text("{ this is not json")
    result = _run(INSTALL_SH, fake_home)
    assert result.returncode != 0
    # File left untouched
    assert settings_file.read_text() == "{ this is not json"


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

def test_uninstall_removes_streamdeck_entries(fake_home):
    _run(INSTALL_SH, fake_home)
    assert _count_streamdeck_entries(_read_settings(fake_home)) == 3

    result = _run(UNINSTALL_SH, fake_home)
    assert result.returncode == 0, result.stderr
    assert _count_streamdeck_entries(_read_settings(fake_home)) == 0


def test_uninstall_preserves_other_hooks(fake_home):
    """After uninstall, peon-ping and unrelated entries must remain."""
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir()
    existing = {
        "hooks": {
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": "/path/to/peon-ping.sh", "timeout": 10}
                    ],
                }
            ]
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(existing))

    _run(INSTALL_SH, fake_home)
    _run(UNINSTALL_SH, fake_home)
    settings = _read_settings(fake_home)

    stop_cmds = [h["command"] for entry in settings["hooks"]["Stop"] for h in entry["hooks"]]
    assert "/path/to/peon-ping.sh" in stop_cmds, "peon-ping entry was clobbered"


def test_uninstall_no_settings_is_noop(fake_home):
    """No settings.json → uninstall is a clean no-op, no error."""
    result = _run(UNINSTALL_SH, fake_home)
    assert result.returncode == 0
    assert not (fake_home / ".claude" / "settings.json").exists()
