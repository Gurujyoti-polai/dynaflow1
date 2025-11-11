import os
import importlib.util
from typing import Dict
from core.plugins.base import PluginBase
from core.config import Config

class PluginRegistry:
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
    
    def register(self, plugin: PluginBase):
        """Register a plugin instance"""
        self.plugins[plugin.name] = plugin
        print(f"✅ Registered plugin: {plugin.name}")
    
    def get(self, name: str) -> PluginBase:
        """Get plugin by name"""
        return self.plugins.get(name)
    
    def list_plugins(self) -> Dict[str, Dict]:
        """List all registered plugins"""
        return {
            name: {
                "description": plugin.description,
                "actions": plugin.get_available_actions()
            }
            for name, plugin in self.plugins.items()
        }
    
    def load_from_directory(self, directory: str):
        """Dynamically load plugins from directory"""
        if not os.path.exists(directory):
            os.makedirs(directory)
            return
        
        for filename in os.listdir(directory):
            if filename.endswith("_plugin.py") and not filename.startswith("_"):
                filepath = os.path.join(directory, filename)
                module_name = filename[:-3]
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for Plugin class
                    if hasattr(module, "Plugin"):
                        plugin_class = getattr(module, "Plugin")
                        plugin_instance = plugin_class()
                        self.register(plugin_instance)
                except Exception as e:
                    print(f"❌ Failed to load plugin {filename}: {e}")

# Global registry
plugin_registry = PluginRegistry()