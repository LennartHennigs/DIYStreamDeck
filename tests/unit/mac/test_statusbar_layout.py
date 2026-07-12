"""Tests for the menu-bar app's key_def layout formatter."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.mac.layout_formatter import layout_for_app, describe_key, layout_lines

KEY_DEF = {
    "applications": {
        "_default": {
            "14": {"key_sequence": "GUI+TAB", "color": "yellow", "description": "Previous App"},
            "0": {"key_sequence": "GUI+A", "color": "red", "description": "Default Select All"},
        },
        "_otherwise": {
            "11": {"string": "TODO: ", "color": "#0080FF", "description": "Type snippet"},
        },
        "Finder": {
            "0": {"key_sequence": "GUI+N", "color": "green", "description": "New Folder"},
            "3": {"folder": "apps", "color": "white", "description": "Apps"},
        },
        "Notizen": {"alias_of": "Finder"},
        "Standalone": {
            "ignore_default": True,
            "1": {"action": "spotify.play", "color": "green", "description": "Play"},
        },
    }
}


def test_app_section_merged_with_default():
    layout = dict(layout_for_app(KEY_DEF, "Finder"))
    assert layout[0]["description"] == "New Folder"  # app key wins over _default key 0
    assert layout[14]["description"] == "Previous App"  # _default merged in
    assert 3 in layout


def test_unknown_app_falls_back_to_otherwise():
    layout = dict(layout_for_app(KEY_DEF, "UnknownApp"))
    assert 11 in layout
    assert layout[14]["description"] == "Previous App"


def test_alias_resolves_to_target():
    assert layout_for_app(KEY_DEF, "Notizen") == layout_for_app(KEY_DEF, "Finder")


def test_ignore_default_skips_default_keys():
    layout = dict(layout_for_app(KEY_DEF, "Standalone"))
    assert 1 in layout
    assert 14 not in layout


def test_describe_key_variants():
    assert describe_key({"description": "Close Tab", "key_sequence": "GUI+W"}) == "Close Tab (GUI+W)"
    assert describe_key({"description": "Save+Enter",
                         "key_sequence": ["GUI+S", 0.1, "ENTER"]}) == "Save+Enter (GUI+S, 0.1, ENTER)"
    assert describe_key({"description": "Play", "action": "spotify.play"}) == "Play (spotify.play)"
    assert describe_key({"application": "Finder"}) == "launch Finder"
    assert describe_key({}) == "(unassigned)"


def test_layout_lines_are_sorted_and_formatted():
    lines = layout_lines(KEY_DEF, "Finder")
    assert lines[0].startswith("Key  0 — New Folder")
    nums = [int(line[4:6]) for line in lines]
    assert nums == sorted(nums)
