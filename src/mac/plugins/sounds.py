import os
from typing import Dict, Callable, Union, List
from playsound3 import playsound
from src.mac.plugins.base_plugin import BasePlugin


class SoundsPlugin(BasePlugin):
    """Plugin to play local sound files asynchronously.

    Uses playsound3's non-blocking mode: play() returns immediately and the
    returned sound handles are kept so stop() can stop playback that is
    actually in flight (a ThreadPoolExecutor cannot cancel a running sound).
    """

    verbose: bool
    config: Dict[str, Union[str, int]]
    sound_path: str

    def __init__(self, config_file: str, verbose: bool) -> None:
        super().__init__(config_file, verbose)
        self.sound_path = self.config.get('sound_path', '')
        self._sound_base_dir = os.path.realpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), self.sound_path)
        )
        self._sounds: List = []

    def commands(self) -> Dict[str, Callable]:
        return {
            'sounds.play': self.play,
            'sounds.stop': self.stop,
        }

    def play(self, filename: str) -> None:
        # Security: Validate filename to prevent path traversal and injection attacks
        if (not filename or
                '..' in filename or
                filename.startswith('/') or
                '\\' in filename or
                '\x00' in filename or
                any(ord(c) < 32 and c not in '\t\n\r' for c in filename)):
            self._log_and_raise(f"Invalid filename: {filename}")

        safe_filename = os.path.basename(filename)
        resolved_path = os.path.realpath(os.path.join(self._sound_base_dir, safe_filename))

        # Security: Ensure resolved path stays within the sound directory
        if not resolved_path.startswith(self._sound_base_dir):
            self._log_and_raise(f"Invalid file path: {filename}")

        if not os.path.exists(resolved_path):
            self._log_and_raise(f"File {filename} not found.")

        try:
            self._sounds = [s for s in self._sounds if s.is_alive()][-10:]
            self._sounds.append(playsound(resolved_path, block=False))
            if self.verbose:
                print(f"Playing '{filename}'")
        except Exception as e:
            self._log_and_raise(f"Failed to play '{filename}': {e}")

    def stop(self) -> None:
        for sound in list(self._sounds):
            try:
                if sound.is_alive():
                    sound.stop()
            except Exception:
                pass
        self._sounds.clear()
        if self.verbose:
            print("Stopped playback")
