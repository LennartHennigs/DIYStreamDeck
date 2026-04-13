# StreamDeck Improvement Plan

## Summary

This document provides an honest assessment of the DIY StreamDeck project based on a code review conducted in April 2026. The project is a well-built hobby tool that does its job reliably, but several real issues should be addressed before treating it as a reference for others or extending it significantly.

Overall Assessment: ⭐⭐⭐ (Good hobby project)

---

## ✅ Real Achievements

- **Working hardware integration**: Clean Pi Pico ↔ Mac communication over USB serial with heartbeat monitoring and graceful shutdown
- **Sound file security**: `sounds.py` path traversal defence is genuinely correct — multi-layer (blacklist check → basename extraction → realpath canonicalisation → prefix check)
- **Threading**: Proper resource cleanup and graceful shutdown in the Mac watchdog
- **Extensible plugin system**: New plugins are straightforward to add by extending `BasePlugin`
- **Test infrastructure exists**: pytest fixtures, hardware mocking, and CI-ready configuration are in place
- **Config flexibility**: `_default`, `_otherwise`, alias, and folder navigation all work correctly

---

## 🔴 High Priority — Fix These

### 1. Exception swallowing (silent failures)

`code.py` lines ~200–211 and `watchdog.py` ~195 contain bare `except Exception: pass` blocks. Serial writes and app launches fail silently. The user gets no feedback and debugging is very hard.

**Fix**: At minimum, log the exception when `verbose=True`. Preferably surface it as a print to stderr.

### 2. `unload_keypad()` double-call risk (`code.py` ~479)

No guard prevents calling `unload_keypad()` twice. The second call clears hardware that may already be in an undefined state.

**Fix**: Add `if self.unloaded: return` at the top of `unload_keypad()`.

---

## 🟡 Medium Priority — Worth Fixing

### 3. Alias resolution: add explicit hard depth limit (`code.py` lines 351–358)

`load_single_app_config` currently resolves exactly one alias level and stops — this works correctly today. However there is no explicit guard, so a future change could accidentally introduce recursion. A misconfigured alias chain should fail fast with a clear error.

**Fix**: Add a `max_depth=1` parameter and assert it is not exceeded. If depth exceeded, print a clear error and return `None`.

### 4. AppleScript injection risk (`watchdog.py` ~lines 105–130)

`app_name` is interpolated directly into an AppleScript string. The `command_dict` allowlist prevents misuse today, but if the allowlist is ever extended without adding escaping the risk appears.

**Fix**: Escape `"` → `\"` in `app_name` before interpolation, regardless of allowlist.

### 5. Inconsistent error handling across plugins

`hue.py` uses bare `print()`, `sounds.py` uses `_log_and_raise()`, Spotify swallows exceptions. No shared strategy.

**Fix**: Settle on one approach (logging + re-raise, or logging + return `None`). Apply consistently.

---

## 🔵 Low Priority — Optional Improvements

### 6. Testing quality

Test count (190+) is high but several tests assert on `Mock()` properties rather than real behaviour, and at least one test file inspects source code with regex rather than running code. Mocks are shallow (e.g. Hue light mock exposes only `name` and `on` vs. 20+ real properties).

**Improvements**:

- Remove or replace trivial mock-on-mock tests
- Add at least one integration-style test per plugin covering a real error path
- Deepen mock shapes to match real API responses

### 7. Architecture coupling

`WatchDog` imports Cocoa, `serial`, `subprocess`, and plugin system directly. This ties everything to macOS and makes unit testing require mocking the entire OS. Not a problem for a personal tool, but limits portability and testability.

### 8. Documentation gaps

README covers setup well but is missing:

- Serial protocol spec (message format, timing, heartbeat interval)
- State machine for app switching and folder navigation
- Thread safety model
- What happens to key bindings when config is partially invalid

### 9. `launch_app()` validation gaps (`watchdog.py` ~184–197)

Blocks `/`, `\`, `\x00` but not leading dashes (option injection to `open -a`).

**Fix**: Reject app names that start with `-`.

---

## 🚫 Not Recommended

- **Splitting `KeyController` into multiple files**: On CircuitPython, each additional file costs RAM and import time on the Pico. The monolith is the right approach for this hardware.

---

## Known Limitations

These are structural constraints, not bugs — worth knowing before extending the project:

- **macOS only**: The Mac watchdog depends on Cocoa/NSWorkspace and cannot run on Windows or Linux without a rewrite
- **No integration tests**: All tests mock serial, Cocoa, and plugins. The serial roundtrip and real app-switching behaviour are not tested
- **Plugin interface is minimal**: `BasePlugin` has no type hints, no lifecycle hooks, and no dependency injection — fine for the current three plugins but would need work for a larger set
- **Plugin discovery is hardcoded**: `watchdog.py` matches filenames directly rather than using a registry

---

## Future Enhancements (Optional)

These are ideas, not gaps:

- Web-based configuration interface
- Configuration backup/restore
- Visual LED animation system
- Multi-platform support (Windows/Linux)
- Plugin marketplace

---

## Ratings

| Category | Rating | Notes |
| --- | --- | --- |
| Code Quality | ⭐⭐⭐ | Works well; exception swallowing and inconsistent error handling are the main rough edges |
| Security | ⭐⭐⭐ | `sounds.py` path traversal defence is solid; AppleScript and `launch_app` validation are shallow |
| Testing | ⭐⭐½ | High quantity hides shallow quality; mocks are weak and no integration tests exist |
| Documentation | ⭐⭐⭐ | Good setup docs; design/protocol docs missing |
| Overall | ⭐⭐⭐ | Good hobby project with real rough edges |

---

Assessment completed April 2026
