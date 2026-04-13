# Run the Mac watchdog

This file explains how to bootstrap a venv and run the Mac watchdog using the
provided launcher `run-mac-watchdog.sh`.

Bootstrap and run (zsh):

```bash
# create and activate a local venv
python3 -m venv .venv
source .venv/bin/activate

# upgrade pip and install dependencies from req.txt (if present)
python -m pip install --upgrade pip
if [ -f req.txt ]; then
  python -m pip install -r req.txt
fi

# run the watchdog (replace the serial port with your device)
./run-mac-watchdog.sh --port /dev/tty.usbmodemXXXX --speed 9600 --verbose
```

## Notes

- The launcher prepends `./src` to `PYTHONPATH` so you don't need to `pip install` the project to run it.
- If `.venv` exists the launcher will use its Python and packages automatically.
- On macOS installing `pyobjc` may require Xcode command-line tools.
- Serial devices are typically under `/dev/tty.*` or `/dev/cu.*` on macOS; use
  `ls /dev/tty.* /dev/cu.*` to find your device.
