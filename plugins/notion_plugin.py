import os
from core.plugins.base import PluginBase
from notion_client import Client
from typing import Dict, Any

class Plugin(PluginBase):
    @property
    def name(self) -> str:
        return "notion"

    @property
    def description(self) -> str:
        return "Create pages or write data into Notion"

    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        token = config.get("token") or os.getenv("NOTION_TOKEN")
        database_id = config.get("database_id") or os.getenv("NOTION_DB_ID")

        if not token or not database_id:
            return {"error": "Missing NOTION_TOKEN or NOTION_DB_ID"}

        notion = Client(auth=token)

        if mode == "mock":
            return {"status": "success", "mock": True, "action": action, "config": config}

        try:
            if action == "create_page":
                title = config.get("title", "Untitled")
                content = config.get("content", "No content provided")

                page = notion.pages.create(
                    parent={"database_id": database_id},
                    properties={
                        "Name": {"title": [{"text": {"content": title}}]}
                    },
                    children=[
                        {"object": "block", "type": "paragraph", "paragraph": {"text": [{"type": "text", "text": {"content": content}}]}}
                    ]
                )
                return {"status": "success", "page_id": page.get("id")}
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    def get_available_actions(self) -> Dict[str, str]:
        return {"create_page": "Create a Notion page in a database"}
