# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck

from abc import ABC, abstractmethod
import os

class BasePlugin(ABC):
    
    @abstractmethod
    def commands(self):
        """
        Returns a dictionary where keys are command names and values are
        callable functions that implement the command.
        """
        pass

    
    def _log_and_raise(self, msg: str) -> None:
        print(msg)
        raise Exception(msg)
    

    def _ping(self, ip: str) -> bool:
        return os.system(f"ping -c 1 -W 2 {ip} > /dev/null 2>&1") == 0   
    
