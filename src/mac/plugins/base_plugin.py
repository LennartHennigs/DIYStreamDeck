# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck

from abc import ABC, abstractmethod
import ipaddress
import subprocess
import logging
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
        logging.error(msg)
        raise Exception(msg)

    def _ping(self, ip: str) -> bool:
        """Safely ping an IP address. Returns True if reachable, False otherwise.

        Validates that `ip` is a proper IPv4/IPv6 address before calling ping.
        Uses subprocess.run with an argument list to avoid shell interpolation.
        """
        try:
            # validate IP address
            ipaddress.ip_address(ip)
        except ValueError:
            logging.warning("Invalid IP address provided to _ping: %s", ip)
            return False

        try:
            result = subprocess.run(["ping", "-c", "1", "-W", "2", ip],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    check=False)
            return result.returncode == 0
        except Exception:
            logging.exception("Ping failed due to unexpected error")
            return False
    
