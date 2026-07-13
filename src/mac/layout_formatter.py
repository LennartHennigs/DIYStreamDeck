# DIY Streamdeck — key_def.json layout formatter (Mac side)
# https://github.com/LennartHennigs/DIYStreamDeck
"""Read-only formatter for key_def.json used by the menu-bar app's cheat sheet.

Mirrors the Pico's layout resolution just enough for display purposes:
app section (with alias_of) or _otherwise fallback, merged with _default
unless ignore_default is set. Does not validate — the firmware owns that.
"""
import json
import os
from typing import Dict, List, Optional, Tuple

_cache: Dict[str, Tuple[float, dict]] = {}  # path -> (mtime, parsed)

# Mirror of the Pico's NAMED_COLORS (src/pi_pico/code.py) so the cheat sheet
# dots match the LED colors. "black" maps to off — treated as no dot below.
NAMED_COLORS: Dict[str, Tuple[int, int, int]] = {
    "black":   (0, 0, 0),
    "white":   (255, 255, 255),
    "red":     (255, 0, 0),
    "green":   (0, 255, 0),
    "blue":    (0, 0, 255),
    "yellow":  (255, 255, 0),
    "orange":  (255, 165, 0),
    "cyan":    (0, 255, 255),
    "magenta": (255, 0, 255),
    "purple":  (128, 0, 128),
    "pink":    (255, 105, 180),
    "gray":    (128, 128, 128),
    "grey":    (128, 128, 128),
}


def color_to_rgb(color) -> Optional[Tuple[int, int, int]]:
    """Resolve a key_def color (named or '#RRGGBB') to an (r, g, b) tuple.

    Returns None for a missing color or "black"/(0,0,0) (LED off — no dot shown).
    """
    if not color or not isinstance(color, str):
        return None
    name = color.strip().lower()
    if name in NAMED_COLORS:
        rgb = NAMED_COLORS[name]
    elif name.startswith("#") and len(name) == 7:
        try:
            rgb = (int(name[1:3], 16), int(name[3:5], 16), int(name[5:7], 16))
        except ValueError:
            return None
    else:
        return None
    return None if rgb == (0, 0, 0) else rgb  # black / off → no dot


def load_key_def(path: str) -> dict:
    # mtime cache: called on every app switch; reparse only after edits
    mtime = os.stat(path).st_mtime
    cached = _cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    with open(path, 'r') as f:
        data = json.load(f)
    _cache[path] = (mtime, data)
    return data


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


def _numeric_keys(section: dict) -> Dict[int, dict]:
    keys = {}
    for key, item in section.items():
        try:
            num = int(key)
        except (TypeError, ValueError):
            continue  # ignore_default, alias_of, autoclose, ...
        if 0 <= num <= 15 and isinstance(item, dict):
            keys[num] = item
    return keys


def layout_for_app(key_def: dict, app_name: str) -> List[Tuple[int, dict]]:
    """Return the (key_number, key_config) pairs shown for an app, sorted."""
    apps = key_def.get("applications", {})
    section: Optional[dict] = apps.get(app_name)
    if section is not None and "alias_of" in section:
        section = apps.get(section["alias_of"])
    if section is None:
        section = apps.get("_otherwise", {})

    merged = _numeric_keys(section)
    if not _as_bool(section.get("ignore_default", False)):
        for num, item in _numeric_keys(apps.get("_default", {})).items():
            merged.setdefault(num, item)
    return sorted(merged.items())


def describe_key(item: dict) -> str:
    """One-line human description of a key config: 'Close Tab (GUI+W)'."""
    desc = item.get("description", "")
    hint = ""
    if item.get("key_sequence"):
        seq = item["key_sequence"]
        hint = ", ".join(str(s) for s in seq) if isinstance(seq, list) else str(seq)
    elif item.get("action"):
        hint = str(item["action"])
    elif item.get("application"):
        hint = f"launch {item['application']}"
    elif item.get("folder"):
        hint = f"folder {item['folder']}"
    elif item.get("string"):
        hint = f"type {item['string']!r}"
    if desc and hint:
        return f"{desc} ({hint})"
    return desc or hint or "(unassigned)"


def layout_lines(key_def: dict, app_name: str) -> List[str]:
    """Menu-ready lines: 'Key  3 — Close Tab (GUI+W)'."""
    return [f"Key {num:2d} — {describe_key(item)}"
            for num, item in layout_for_app(key_def, app_name)]


def layout_entries(
    key_def: dict, app_name: str
) -> List[Tuple[int, str, Optional[Tuple[int, int, int]]]]:
    """Cheat-sheet rows as (key_number, description, rgb_or_None).

    The rgb is the key's resolved LED color for a colored dot; None means no
    color / LED off (caller shows the row without a dot)."""
    return [(num, describe_key(item), color_to_rgb(item.get("color")))
            for num, item in layout_for_app(key_def, app_name)]
