from abc import ABC, abstractmethod
from typing import Dict, Any

class ToolBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        pass
    
    # 🔹 ADD THIS
    def get_schema(self) -> Dict[str, Any]:
        """
        Override this to provide detailed schema for QUERY_TOOL.
        Default implementation returns minimal info.
        """
        return {
            "tool": self.name,
            "description": self.description,
            "actions": {}  # Tools should override with their actions
        }