# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck

import json
from abc import ABC, abstractmethod
from typing import Dict, Callable


class BasePlugin(ABC):
    """Abstract base class for plugins.

    Plugins must implement `commands()` which returns a mapping of command
    names to callables.
    """

    def __init__(self, config_file: str, verbose: bool = False) -> None:
        self.verbose = verbose
        self.config = self._load_config(config_file)

    @abstractmethod
    def commands(self) -> Dict[str, Callable]:
        """Return a dict mapping command names to callables."""
        raise NotImplementedError

    def _load_config(self, config_file: str) -> dict:
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self._log_and_raise(f"Config file {config_file} not found.")
        except json.JSONDecodeError:
            self._log_and_raise(
                f"Failed to parse config file {config_file}. Please check if it is a valid JSON file."
            )

    def _log_and_raise(self, msg: str) -> None:
        self._log(msg)
        raise Exception(msg)

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

