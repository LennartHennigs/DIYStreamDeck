# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck

from abc import ABC, abstractmethod

class BasePlugin(ABC):
    
    @abstractmethod
    def commands(self):
        """
        Returns a dictionary where keys are command names and values are
        callable functions that implement the command.
        """
        pass
