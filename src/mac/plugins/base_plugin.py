from abc import ABC, abstractmethod

class BasePlugin(ABC):
    
    @abstractmethod
    def commands(self):
        """
        Returns a dictionary where keys are command names and values are
        callable functions that implement the command.
        """
        pass
