# tools/__init__.py

from typing import Dict, Optional
from tools.base import ToolBase


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolBase] = {}

    def register(self, tool: ToolBase):
        """Manually register a tool"""
        self._tools[tool.name] = tool
        print(f"✅ Registered tool: {tool.name}")

    def load_tools(self):
        """Load all tools explicitly"""
        print("🔍 Loading tools...")
        
        # Import and register primitives
        try:
            from tools.primitives.http import HTTPTool
            self.register(HTTPTool())
        except Exception as e:
            print(f"⚠️  Failed to load HTTPTool: {e}")
        
        try:
            from tools.primitives.data import DataTool
            self.register(DataTool())
        except Exception as e:
            print(f"⚠️  Failed to load DataTool: {e}")
        
        try:
            from tools.primitives.file import FileTool
            self.register(FileTool())
        except Exception as e:
            print(f"⚠️  Failed to load FileTool: {e}")
        
        # Import and register integrations
        try:
            from tools.integrations.notion import NotionTool
            self.register(NotionTool())
        except Exception as e:
            print(f"⚠️  Failed to load NotionTool: {e}")

        try:
            from tools.integrations.github import GithubTool
            self.register(GithubTool())
        except Exception as e:
            print(f"⚠️  Failed to load GithubTool: {e}")

    def get(self, name: str) -> Optional[ToolBase]:
        """Get tool by name"""
        return self._tools.get(name)

    def list_manifest(self) -> str:
        """Lightweight manifest for agent prompt"""
        if not self._tools:
            return "No tools loaded"
            
        primitives = []
        integrations = []

        for tool in self._tools.values():
            line = f"- {tool.name}: {tool.description}"
            if tool.category == "primitive":
                primitives.append(line)
            else:
                integrations.append(line)

        manifest = "Primitives (always available):\n"
        manifest += "\n".join(primitives) if primitives else "  None"
        manifest += "\n\nIntegrations (query for actions):\n"
        manifest += "\n".join(integrations) if integrations else "  None"

        return manifest

    def list_all(self) -> Dict[str, Dict[str, str]]:
        """Return all tools with metadata"""
        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category
            }
            for name, tool in self._tools.items()
        }


# Create and auto-load registry
print("🚀 Initializing tool registry...")
registry = ToolRegistry()
registry.load_tools()
print(f"📦 Loaded {len(registry._tools)} tools total\n")

# Export for use in other modules
__all__ = ['registry', 'ToolBase', 'ToolRegistry']