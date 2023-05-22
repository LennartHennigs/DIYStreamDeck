import os
import json
from typing import Dict, Callable, Union
from playsound import playsound
from concurrent.futures import ThreadPoolExecutor
from base_plugin import BasePlugin


class SoundsPlugin(BasePlugin):
    verbose: bool
    config: Dict[str, Union[str, int]]
    executor: ThreadPoolExecutor
    sound_path: str

    def __init__(self, config_file: str, verbose: bool) -> None:
        self.verbose = verbose
        self.config = self._load_config(config_file)
        self.sound_path = self.config.get('sound_path', '')
        self.executor = ThreadPoolExecutor(max_workers=2)

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
        try:
            
            full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.sound_path, filename)
            if not os.path.exists(full_path):
                self._log_and_raise(f"File {filename} not found.")
            self.executor.submit(playsound, full_path)
            if self.verbose:
                print(f"Playing '{filename}'")
        except Exception as e:
            self._log_and_raise(f"Failed to play '{filename}': {e}")

    def stop(self) -> None:
        try:
            # Cancel all futures
            for future in self.executor.futures:
                future.cancel()
            if self.verbose:
                print(f"Stopped all playback")
        except Exception as e:
            self._log_and_raise(f"Failed to stop playback: {e}")
