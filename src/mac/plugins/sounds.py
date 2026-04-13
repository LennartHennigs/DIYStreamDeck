import os
import json
from typing import Dict, Callable, Union, List
from playsound import playsound
from concurrent.futures import ThreadPoolExecutor, Future
from src.mac.plugins.base_plugin import BasePlugin


class SoundsPlugin(BasePlugin):
    """Plugin to play local sound files asynchronously.

    Tracks submitted futures so playback can be cancelled and executor
    shut down cleanly.
    """

    verbose: bool
    config: Dict[str, Union[str, int]]
    executor: ThreadPoolExecutor
    sound_path: str

    def __init__(self, config_file: str, verbose: bool) -> None:
        self.verbose = verbose
        self.config = self._load_config(config_file)
        self.sound_path = self.config.get('sound_path', '')
        self.executor = ThreadPoolExecutor(max_workers=2)
        # Keep track of submitted futures so we can cancel them on stop()
        self._futures: List[Future] = []

    def commands(self) -> Dict[str, Callable]:
        return {
            'sounds.play': self.play,
            'sounds.stop': self.stop,
        }

    def _load_config(self, config_file: str) -> Dict[str, Union[str, int]]:
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self._log_and_raise(f"Config file {config_file} not found.")
        except json.JSONDecodeError:
            self._log_and_raise(
                f"Failed to parse config file {config_file}. Please check if it is a valid JSON file."
            )

    def _log_and_raise(self, message: str) -> None:
        if self.verbose:
            print(message)
        raise Exception(message)

    def play(self, filename: str) -> None:
        # Security: Validate filename to prevent path traversal and injection attacks
        if (not filename or
                '..' in filename or
                filename.startswith('/') or
                '\\' in filename or
                '\x00' in filename or
                any(ord(c) < 32 and c not in '\t\n\r' for c in filename)):
            self._log_and_raise(f"Invalid filename: {filename}")

        # Use basename to strip any path components
        safe_filename = os.path.basename(filename)

        # Construct and resolve the full path
        sound_base_dir = os.path.realpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), self.sound_path)
        )
        resolved_path = os.path.realpath(os.path.join(sound_base_dir, safe_filename))

        # Security: Ensure resolved path stays within the sound directory
        if not resolved_path.startswith(sound_base_dir):
            self._log_and_raise(f"Invalid file path: {filename}")

        if not os.path.exists(resolved_path):
            self._log_and_raise(f"File {filename} not found.")

        try:
            future = self.executor.submit(playsound, resolved_path)
            self._futures.append(future)
            if self.verbose:
                print(f"Playing '{filename}'")
        except Exception as e:
            self._log_and_raise(f"Failed to play '{filename}': {e}")

    def stop(self) -> None:
        for future in list(self._futures):
            try:
                future.cancel()
            except Exception:
                pass
        self._futures.clear()
        self.executor.shutdown(wait=False)
        self.executor = ThreadPoolExecutor(max_workers=2)
        if self.verbose:
            print("Stopped playback")
