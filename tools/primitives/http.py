from tools.base import ToolBase
import httpx
import os
import re
from typing import Dict, Any


class HTTPTool(ToolBase):

    @property
    def name(self) -> str:
        return "http"

    @property
    def description(self) -> str:
        return "HTTP requests (GET, POST, PUT, DELETE)"

    @property
    def category(self) -> str:
        return "primitive"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "description": self.description,
            "category": self.category,
            "actions": {
                "GET": {
                    "description": "HTTP GET request",
                    "parameters": {
                        "url": {"type": "string", "required": True},
                        "headers": {"type": "object", "required": False}
                    },
                    "example": {
                        "url": "https://api.example.com/data",
                        "headers": {"Authorization": "Bearer {{TOKEN}}"}
                    }
                },
                "POST": {
                    "description": "HTTP POST request",
                    "parameters": {
                        "url": {"type": "string", "required": True},
                        "headers": {"type": "object", "required": False},
                        "body": {"type": "object", "required": False}
                    },
                    "example": {
                        "url": "https://api.example.com/resource",
                        "headers": {
                            "Content-Type": "application/json",
                            "Notion-Version": "2022-06-28"
                        },
                        "body": {"key": "value"}
                    }
                },
                "PUT": {
                    "description": "HTTP PUT request",
                    "parameters": {
                        "url": {"type": "string", "required": True},
                        "headers": {"type": "object", "required": False},
                        "body": {"type": "object", "required": False}
                    }
                },
                "DELETE": {
                    "description": "HTTP DELETE request",
                    "parameters": {
                        "url": {"type": "string", "required": True},
                        "headers": {"type": "object", "required": False}
                    }
                }
            }
        }

    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        method = action.upper()
        if method not in ["GET", "POST", "PUT", "DELETE"]:
            return {"error": f"Unsupported HTTP method: {method}"}

        # Get parameters - accept both 'body' and 'data' for backward compatibility
        url = config.get("url", "")
        headers = config.get("headers", {})
        body = config.get("body") or config.get("data")  # Accept both

        # Replace env vars
        url = self._replace_env(url)
        headers = self._replace_env_in_dict(headers)
        body = self._replace_env_in_dict(body) if body else None

        if mode == "mock":
            return {"mock": True, "method": method, "url": url}

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if body else None
                )

            try:
                data = response.json()
            except:
                data = response.text

            return {
                "status": response.status_code,
                "data": data
            }

        except httpx.HTTPStatusError as e:
            return {
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
                "status": e.response.status_code
            }
        except Exception as e:
            return {"error": str(e)}

    def _replace_env(self, text: str) -> str:
        """Replace {{VAR}} with environment variable"""
        if not isinstance(text, str):
            return text
        
        pattern = r'\{\{([A-Z_0-9]+)\}\}'
        
        def replacer(match):
            var_name = match.group(1)
            env_value = os.getenv(var_name)
            if env_value:
                return env_value
            else:
                print(f"⚠️  Warning: {var_name} not found in environment")
                return match.group(0)
        
        return re.sub(pattern, replacer, text)

    def _replace_env_in_dict(self, data):
        """Recursively replace env vars in dict/list/str"""
        if isinstance(data, dict):
            return {k: self._replace_env_in_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_env_in_dict(i) for i in data]
        elif isinstance(data, str):
            return self._replace_env(data)
        else:
            return data