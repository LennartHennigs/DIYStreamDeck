# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck

from abc import ABC, abstractmethod
from typing import Dict, Callable


class BasePlugin(ABC):
    """Abstract base class for plugins.

    Plugins must implement `commands()` which returns a mapping of command
    names to callables.
    """

    @abstractmethod
    def commands(self) -> Dict[str, Callable]:
        """Return a dict mapping command names to callables."""
        raise NotImplementedError

    def _log_and_raise(self, msg: str) -> None:
        import logging
        logging.error(msg)
        raise Exception(msg)
    
