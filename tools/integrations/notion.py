# tools/integrations/notion.py

from typing import Dict, Any
import httpx
import os

from tools.base import ToolBase


class NotionTool(ToolBase):

    @property
    def name(self) -> str:
        return "notion"

    @property
    def description(self) -> str:
        return "Notion API integration for pages and databases"
    
    @property
    def category(self) -> str:
        return "integration"

    # =========================
    # 🔹 SCHEMA (FOR QUERY_TOOL)
    # =========================
    def get_schema(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "description": self.description,
            "actions": {
                "create_page": {
                    "description": "Create a page inside a Notion database",
                    "required_env": ["NOTION_TOKEN", "NOTION_DB_ID"],
                    "parameters": {
                        "parent": {
                            "type": "object",
                            "required": True,
                            "description": "Database or page parent"
                        },
                        "properties": {
                            "type": "object",
                            "required": True,
                            "description": "Page properties"
                        }
                    },
                    "example": {
                        "parent": {
                            "database_id": "{{NOTION_DB_ID}}"
                        },
                        "properties": {
                            "Name": {
                                "title": [
                                    {
                                        "text": {
                                            "content": "My Page"
                                        }
                                    }
                                ]
                            }
                        }
                    }
                },

                "update_page": {
                    "description": "Update properties of an existing page",
                    "required_env": ["NOTION_TOKEN"],
                    "parameters": {
                        "page_id": {
                            "type": "string",
                            "required": True
                        },
                        "properties": {
                            "type": "object",
                            "required": True
                        }
                    }
                },

                "query_database": {
                    "description": "Query a Notion database",
                    "required_env": ["NOTION_TOKEN"],
                    "parameters": {
                        "database_id": {
                            "type": "string",
                            "required": True
                        },
                        "filter": {
                            "type": "object",
                            "required": False
                        }
                    }
                }
            }
        }

    # =========================
    # 🔹 EXECUTION
    # =========================
    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        if mode == "mock":
            return {
                "status": "mock",
                "tool": self.name,
                "action": action,
                "config": config
            }

        token = os.getenv("NOTION_TOKEN")
        if not token:
            return {"error": "NOTION_TOKEN not set"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

        try:
            if action == "create_page":
                return self._create_page(headers, config)

            elif action == "update_page":
                return self._update_page(headers, config)

            elif action == "query_database":
                return self._query_database(headers, config)

            else:
                return {"error": f"Unknown Notion action: {action}"}

        except Exception as e:
            return {"error": str(e)}

    # =========================
    # 🔹 INTERNAL METHODS
    # =========================
    def _create_page(self, headers, config):
        url = "https://api.notion.com/v1/pages"

        with httpx.Client(timeout=30) as client:
            r = client.post(url, headers=headers, json=config)
            r.raise_for_status()
            return r.json()

    def _update_page(self, headers, config):
        page_id = config.pop("page_id")
        url = f"https://api.notion.com/v1/pages/{page_id}"

        with httpx.Client(timeout=30) as client:
            r = client.patch(url, headers=headers, json=config)
            r.raise_for_status()
            return r.json()

    def _query_database(self, headers, config):
        database_id = config.pop("database_id")
        url = f"https://api.notion.com/v1/databases/{database_id}/query"

        with httpx.Client(timeout=30) as client:
            r = client.post(url, headers=headers, json=config)
            r.raise_for_status()
            return r.json()
