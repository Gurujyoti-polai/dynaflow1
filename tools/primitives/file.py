import os
from typing import Dict, Any
from tools.base import ToolBase


class FileTool(ToolBase):

    @property
    def name(self) -> str:
        return "file"

    @property
    def description(self) -> str:
        return "Read and write local files"

    @property
    def category(self) -> str:
        return "primitive"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "description": self.description,
            "category": self.category,
            "actions": {
                "read": {
                    "description": "Read contents of a file",
                    "parameters": {
                        "path": {"type": "string", "required": True}
                    },
                    "example": {
                        "path": "data/input.txt"
                    }
                },
                "write": {
                    "description": "Write content to a file",
                    "parameters": {
                        "path": {"type": "string", "required": True},
                        "content": {"type": "string", "required": True}
                    },
                    "example": {
                        "path": "data/output.txt",
                        "content": "Hello World"
                    }
                }
            }
        }

    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:

        if action == "read":
            path = config.get("path")
            if not path:
                return {"error": "Missing 'path' for file read"}

            if mode == "mock":
                return {"status": "mock", "content": f"(mocked content from {path})"}

            if not os.path.exists(path):
                return {"error": f"File not found: {path}"}

            with open(path, "r") as f:
                content = f.read()
            return {"status": "success", "content": content}

        elif action == "write":
            path = config.get("path")
            content = config.get("content", "")

            if not path:
                return {"error": "Missing 'path' for file write"}

            if mode == "mock":
                return {"status": "mock", "message": f"Would write to {path}"}

            with open(path, "w") as f:
                f.write(content)

            return {"status": "success", "message": f"Wrote file: {path}"}

        else:
            return {"error": f"Unknown action: {action}"}