# DIY Streamdeck with the Pimoroni RGB Keypad

A Raspberry Pi Pico + [Pimoroni RGB Keypad](https://shop.pimoroni.com/products/pico-rgb-keypad-base) that provides dynamic, app-specific shortcut keys driven by a Mac watchdog script.

![Keypad with Zoom Shortcuts](images/keypad.png)

If you find this useful, consider giving it a ⭐️ on [GitHub](https://github.com/LennartHennigs/DIYStreamDeck) or [buying me a ☕️](https://ko-fi.com/lennart0815).

---

## Features

- App-specific key layouts that switch automatically when you change applications
- Four key types: **shortcut**, **application launch**, **folder** (sub-pages), and **action** (plugin commands)
- Global `_default` keys added to every app/folder, with per-entry opt-out via `ignore_default`
- Fallback `_otherwise` layout for apps without a specific definition
- Plugins for Spotify, Philips Hue, audio playback, and **Claude Code hooks** (light the keypad on turn-end / permission-prompt / API-error — the color persists until you switch apps or press a key)
- Watchdog heartbeat keeps the keypad "loaded"; disconnect the Mac and the LEDs go dark until the watchdog runs again
- Rotate the layout CW or CCW for 3D-printed cases
- All configuration lives in a single [`key_def.json`](src/pi_pico/key_def.json) on the Pico

---

## Hardware

- Raspberry Pi Pico
- Pimoroni RGB Keypad for Raspberry Pi Pico
- Micro-USB cable
- A Mac running `watchdog.py` (required for app detection and plugins)

---

## How It Works

**`code.py`** (CircuitPython, runs on the Pico) reads `key_def.json` and maps keys to sequences and LED colors. It listens over USB serial for the active app name and updates the layout accordingly.

**`watchdog.py`** (Python, runs on Mac) monitors the active application using Cocoa notifications and sends it to the Pico. It also handles plugin commands. Without it, the keypad works as a static shortcut pad only.

---

## Scripts

| Script | Purpose |
| --- | --- |
| `run-mac-watchdog.sh` | Launcher for `watchdog.py` — sets PYTHONPATH, forwards flags |
| `deploy-to-pico.sh` | Copy `code.py` + `key_def.json` to the CIRCUITPY volume — **prompts for `sudo` password** (macOS 14+ FAT32 safety remount) |
| `run-config-tool.sh` | Launch the browser-based `key_def.json` editor at `http://localhost:8001` |
| `run-tests.sh` | Activate the test venv and run the pytest suite |
| `test-claude.sh` | Send Claude Code signal colors to a running watchdog for hardware smoke-testing |
| `src/mac/hooks/install-claude-hooks.sh` | Register the Claude Code hook in `~/.claude/settings.json` (idempotent) |
| `src/mac/hooks/uninstall-claude-hooks.sh` | Remove only this repo's entries from `~/.claude/settings.json` |

---

## Getting Started

### Pi Pico

1. [Install CircuitPython](https://learn.adafruit.com/welcome-to-circuitpython/installing-circuitpython) on the Pico.
2. Install required libraries into `lib/`: `adafruit_dotstar.mpy`, `adafruit_hid`, and [rgbkeypad-circuitpython](https://github.com/AngainorDev/rgbkeypad-circuitpython).
3. Copy `src/pi_pico/` to the Pico root.

   **First-time install — CLI:** `./deploy-to-pico.sh` copies `code.py` and `key_def.json` to `/Volumes/CIRCUITPY`. Pass `--code` to deploy only `code.py`, `--keys` to deploy only `key_def.json` (default: both); `--help` prints usage. An optional volume path overrides the default (e.g. `./deploy-to-pico.sh --keys /Volumes/CIRCUITPY1`). It performs a `noasync` remount to prevent FAT32 corruption on macOS 14+, which requires **`sudo` — you will be prompted for your macOS admin password**. The remount is temporary; unplugging and replugging restores normal behaviour, and Thonny works as usual afterward.

   **Iterating on `code.py` — Thonny:** [Thonny](https://thonny.org/) is the easier path once the Pico is set up. Open the file directly from `/Volumes/CIRCUITPY`, edit, save (Cmd-S), and press `Ctrl-D` in the REPL to soft-reboot the Pico. No `sudo`, no remount, no unplugging. This is the fastest inner loop for firmware changes.

   **Also fine:** drag-and-drop in Finder for occasional edits.
4. Edit `key_def.json` to set up your layouts. Key `0` is top-left, `15` is bottom-right. [Thonny](https://thonny.org/) makes this easy.

### Mac Watchdog

```bash
cd src/mac
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run — port is auto-detected
python3 watchdog.py --verbose

# Or specify a port explicitly
python3 watchdog.py --port /dev/cu.usbmodem2101 --verbose
```

Or use the launcher script from the repo root:

```bash
# Auto-detect
./run-mac-watchdog.sh --verbose

# Or specify a port
./run-mac-watchdog.sh --port /dev/cu.usbmodem2101 --verbose
```

**Watchdog flags:**

| Flag | Description |
| --- | --- |
| `--port` | Serial port for the Pico (optional — auto-detected if omitted) |
| `--speed` | Baud rate (default: `9600`) |
| `--verbose` | Print active app name to console |
| `--rotate` | Rotate layout: `CW` or `CCW` |

---

## Configuration (`key_def.json`)

### Browser config tool (optional)

`src/mac/config-tool/` provides a browser-based editor for `key_def.json`. Launch it with:

```bash
./run-config-tool.sh
```

Opens `http://localhost:8001` in your default browser. Easier than hand-editing JSON for larger layouts.

Hand-editing works too — the schema is documented below.

### Schema

The file has four top-level sections: `settings`, `applications`, `folders`, `urls`.

### Settings

```json
{ "settings": { "rotate": "CCW" } }
```

`rotate` accepts `CW`, `CCW`, or omit for no rotation.

### Key Types

| Type | Field | Behaviour |
| --- | --- | --- |
| Shortcut | `key_sequence` | Sends a key combination |
| String | `string` | Types literal text character-by-character |
| App launch | `application` | Opens or focuses an app |
| Folder | `folder` | Opens a sub-page of keys |
| Action | `action` | Runs a plugin command or `close_folder` |

**Common fields** (any key type):

- `color` — LED color, either a `#RRGGBB` hex string or a [named color](#named-colors) (e.g. `"red"`)
- `pressedColor` — color while held
- `toggleColor` — color for toggled/active state
- `description` — label printed in `--verbose` output

<a name="named-colors"></a>
**Named colors** — any color field accepts a name instead of hex (case-insensitive):

| Name | RGB | Name | RGB |
| --- | --- | --- | --- |
| `black` | `0,0,0` | `magenta` | `255,0,255` |
| `white` | `255,255,255` | `orange` | `255,165,0` |
| `red` | `255,0,0` | `purple` | `128,0,128` |
| `green` | `0,255,0` | `pink` | `255,105,180` |
| `blue` | `0,0,255` | `gray` / `grey` | `128,128,128` |
| `yellow` | `255,255,0` | | |
| `cyan` | `0,255,255` | | |

For any shade not listed, use a `#RRGGBB` hex value.

**Shortcut-specific:**

- `key_sequence` — keycode string `"CTRL+ALT+T"`, array `["CTRL","ALT","T"]`, or array with float delays between presses
- `pressedUntilReleased: true` — holds the key until physically released

**String-specific:**

- `string` — literal text to type (e.g. `"TODO: "`)
- `string_delay` — delay in seconds between characters (default: `0.05`; `0` to type instantly)

**App-specific:**

- `alias_of` — copy another app's layout instead of defining keys

**Folder-specific:**

- `autoclose: false` — keep folder open after a key press (default: auto-closes)
- Folders without `autoclose` must include a `close_folder` action key

**App/folder/URL:**

- `ignore_default: true` — skip global `_default` keys for this entry

### Example

```json
{
  "settings": { "rotate": "CCW" },

  "applications": {
    "_default": {
      "15": { "key_sequence": "GUI+Q", "color": "#FF0000", "description": "Close App" }
    },

    "zoom.us": {
      "0":  { "key_sequence": "GUI+SHIFT+A", "color": "#FFFF00", "description": "Mute/Unmute" },
      "1":  { "key_sequence": "GUI+SHIFT+V", "color": "#FFFF00", "description": "Start/Stop Video" },
      "15": { "key_sequence": ["GUI+W", 0.1, "RETURN"], "color": "#FF0000", "description": "End Meeting" }
    },

    "_otherwise": {
      "0":  { "key_sequence": "GUI+SPACE",       "color": "#FFFFFF", "description": "Spotlight" },
      "4":  { "action": "spotify.prev",           "color": "#00FF00", "description": "Previous" },
      "5":  { "action": "spotify.playpause",      "color": "#00FF00", "description": "Play/Pause" },
      "6":  { "action": "spotify.next",           "color": "#00FF00", "description": "Next" },
      "13": { "folder": "apps",                   "color": "#FFFFFF", "description": "Apps" }
    }
  },

  "folders": {
    "apps": {
      "0":  { "action": "close_folder",  "color": "#FFFFFF", "description": "Close" },
      "12": { "application": "zoom.us",  "color": "#0000FF", "description": "Zoom" },
      "13": { "application": "Slack",    "color": "#FF0000", "description": "Slack" }
    }
  }
}
```

> **Note:** `watchdog.py` detects URL changes only when Chrome or Safari *becomes active*, not on tab switches.

### URL-specific layouts (Safari / Chrome)

The `urls` top-level section maps a domain to a per-key layout, activated when Safari or Google Chrome brings that URL to the frontmost tab. Same key schema as `applications`.

```json
"urls": {
  "github.com": {
    "0": { "key_sequence": "GUI+T", "color": "#FFFFFF", "description": "New tab" }
  }
}
```

### Debugging config errors

Bad key definitions (unknown keycodes, malformed hex colors) don't crash the keypad. The Pico skips the offending key and forwards the error to the Mac watchdog's stdout via the `Output:` protocol, shown as `[Pico] Config error key 7: Invalid hex color '#GGGGGG'`. Run the watchdog with `--verbose` and check its console when a key doesn't behave as expected.

---

## Plugins

Plugins live in `src/mac/plugins/` and extend `BasePlugin`. Config files go in `src/mac/plugins_config/` (git-ignored — copy from the `.json.example` templates).

### Spotify

Requires a Spotify Premium account. Add credentials to `plugins_config/spotify.json`.

| Command | Description |
| --- | --- |
| `spotify.play` | Resume playback |
| `spotify.pause` | Pause |
| `spotify.playpause` | Toggle play/pause |
| `spotify.next` | Next track |
| `spotify.prev` | Previous track |
| `spotify.volume_up` | Volume +10% |
| `spotify.volume_down` | Volume −10% |

### Philips Hue

Set the bridge IP in `plugins_config/hue.json` and press the bridge button on first run. Lamp identifier can be a name in single quotes or a numeric index.

| Command | Description |
| --- | --- |
| `hue.turn_on 'Lamp Name'` | Turn on a light |
| `hue.turn_off 'Lamp Name'` | Turn off a light |
| `hue.toggle 'Lamp Name'` | Toggle a light |

### Sounds

Place `.wav` or `.mp3` files in `src/mac/sounds/` (configure path in `plugins_config/sounds.json`).

| Command | Description |
| --- | --- |
| `sounds.play 'file.mp3'` | Play a sound file |
| `sounds.stop` | Stop playback |

### Claude (Claude Code integration)

The `claude` plugin lights the whole keypad in traffic-light colors when [Claude Code](https://docs.claude.com/en/docs/claude-code) — Anthropic's terminal-based coding agent — fires lifecycle events. Useful when Claude is doing long-running work in a background tab: green tells you the turn finished, red tells you it's waiting on you, yellow tells you it errored out.

**The color stays lit** until you switch apps, rotate the keypad, press a key, or the next Claude Code event overrides it — the color *is* the status signal, not just an animation. Glance at the keypad ten seconds after Claude finished and you still see the state.

**Events and colors:**

| Claude Code event | Color | What it means |
| --- | --- | --- |
| `Stop` | green | Claude finished a turn without needing anything from you |
| `Notification` | red | Claude needs your attention — a permission prompt is open, or the agent is idle waiting for the next message |
| `StopFailure` | yellow | The turn ended with an API error (rate limit, network, etc.) |

(These are Claude *Code* events — the CLI/terminal agent — not Claude web or desktop.)

#### Install

```bash
# Prereqs
brew install jq                                              # once, if not already installed
cp src/mac/plugins_config/claude.json.example \
   src/mac/plugins_config/claude.json                        # empty defaults are fine

# Register the hook with Claude Code (idempotent — safe to re-run)
./src/mac/hooks/install-claude-hooks.sh
```

The installer:
- Backs up `~/.claude/settings.json` to `~/.claude/settings.json.bak`.
- Appends three entries — one each for `Stop`, `Notification`, `StopFailure` — pointing at `src/mac/hooks/streamdeck-claude.py`.
- Coexists with `peon-ping` and any other Claude Code hooks you have wired up.
- Is idempotent: re-running detects existing entries and doesn't duplicate them.

#### Verify

```bash
./run-mac-watchdog.sh --verbose        # in one terminal — should log 'Loaded plugin: claude'
./test-claude.sh                       # in another — keypad cycles green → red → yellow
```

Then in Claude Code: any turn ending cleanly should turn the keypad green.

#### Uninstall

```bash
./src/mac/hooks/uninstall-claude-hooks.sh
```

Removes only entries pointing at *this repo's* `streamdeck-claude.py`; other hooks (peon-ping etc.) are untouched.

#### Keypad-triggerable test commands

The plugin also exposes `claude.green`, `claude.red`, `claude.yellow` as `action` values in `key_def.json` for hardware testing:

```json
"7": { "action": "claude.green", "color": "#00FF00", "description": "Test claude signal" }
```

<details>
<summary>How it works under the hood</summary>

The watchdog owns the serial port to the Pico exclusively — Claude Code hooks can't write to it directly. So the `claude` plugin runs a background listener on a Unix domain socket (`/tmp/streamdeck-claude.sock`). The hook script writes a one-line datagram (`green`/`red`/`yellow`) to the socket; the plugin validates it and forwards `Claude: <color>` over the serial port under the watchdog's existing lock. The Pico floods all LEDs with the color and holds it until the next `App:`, `Rotate:`, keypress, or `Claude:` line — non-blocking; key scanning never freezes.

If the watchdog isn't running or the Pico is unplugged, the hook silently no-ops so Claude Code isn't slowed down.

</details>

---

## Testing

```bash
# First-time setup
python3 -m venv test_venv && source test_venv/bin/activate
pip install -r tests/requirements_test.txt

# Run tests
./run-tests.sh all       # everything
./run-tests.sh pico      # Pi Pico only
./run-tests.sh mac       # Mac/watchdog only
./run-tests.sh security  # security tests only
```

See [`tests/CLAUDE.md`](tests/CLAUDE.md) for full details.

---

## 3D Printed Case

The case in the photo is [this Printables model](https://www.printables.com/model/80088-pimoroni-keypad-case/). It rotates the keypad — use `"rotate": "CCW"` (or `"CW"`) in `settings` to compensate.
