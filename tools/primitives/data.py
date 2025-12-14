import json
from typing import Dict, Any
from tools.base import ToolBase


class DataTool(ToolBase):

    @property
    def name(self) -> str:
        return "data"

    @property
    def description(self) -> str:
        return "Data extraction and transformation"

    @property
    def category(self) -> str:
        return "primitive"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "description": self.description,
            "category": self.category,
            "actions": {
                "extract": {
                    "description": "Extract data using JSON path (e.g., 'main.temp' or 'weather[0].description')",
                    "parameters": {
                        "data": {"type": "object", "required": True},
                        "path": {"type": "string", "required": True}
                    },
                    "example": {
                        "data": {"main": {"temp": 30}},
                        "path": "main.temp"
                    }
                },
                "uppercase": {
                    "description": "Convert text to uppercase",
                    "parameters": {
                        "text": {"type": "string", "required": True}
                    }
                },
                "lowercase": {
                    "description": "Convert text to lowercase",
                    "parameters": {
                        "text": {"type": "string", "required": True}
                    }
                },
                "json_parse": {
                    "description": "Parse JSON string",
                    "parameters": {
                        "text": {"type": "string", "required": True}
                    }
                }
            }
        }

    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:

        if action == "extract":
            data = config.get("data")
            path = config.get("path")

            if data is None or not path:
                return {"error": "Missing 'data' or 'path' for extract"}

            try:
                value = self._extract_path(data, path)
                return {"status": "success", "result": value}
            except Exception as e:
                return {"error": f"Path extraction failed: {str(e)}"}

        elif action == "uppercase":
            text = config.get("text", "")
            return {"status": "success", "result": text.upper()}

        elif action == "lowercase":
            text = config.get("text", "")
            return {"status": "success", "result": text.lower()}

        elif action == "json_parse":
            raw = config.get("text", "")
            try:
                return {"status": "success", "result": json.loads(raw)}
            except Exception as e:
                return {"error": f"JSON parse failed: {str(e)}"}

        else:
            return {"error": f"Unknown action: {action}"}

    def _extract_path(self, obj, path: str):
        """Walks dot paths and array indices, like: main.temp or weather[0].description"""
        current = obj
        for part in path.split("."):
            if "[" in part:  # array index
                key, index = part.split("[")
                index = int(index[:-1])  # remove ]
                current = current[key][index]
            else:
                current = current[part]
        return current