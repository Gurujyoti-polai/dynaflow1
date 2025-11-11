from abc import ABC, abstractmethod
from typing import Dict, Any

class PluginBase(ABC):
    """Base class for all plugins"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (e.g., 'slack', 'notion')"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description"""
        pass
    
    @abstractmethod
    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        """
        Execute plugin action
        mode: 'real' or 'mock'
        """
        pass
    
    @abstractmethod
    def get_available_actions(self) -> Dict[str, str]:
        """Return dict of available actions and their descriptions"""
        pass