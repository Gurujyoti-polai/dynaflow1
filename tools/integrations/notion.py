# tools/integrations/notion.py

from typing import Dict, Any, Optional
import httpx
import os
import re
from datetime import datetime

from tools.base import ToolBase


class NotionTool(ToolBase):
    """Smart Notion tool that fetches database schema and adapts to property types"""
    
    def __init__(self):
        self._schema_cache: Dict[str, Dict] = {}  # Cache database schemas

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
    # 🔹 SCHEMA
    # =========================
    def get_schema(self) -> Dict[str, Any]:
        """Return schema with simplified parameters for LLM"""
        notion_db_id = os.getenv("NOTION_DB_ID", "NOT_SET")
        
        return {
            "tool": self.name,
            "description": self.description,
            "environment": {
                "NOTION_TOKEN": "✓ Set" if os.getenv("NOTION_TOKEN") else "✗ NOT SET",
                "NOTION_DB_ID": f"✓ Set ({notion_db_id[:8]}...)" if notion_db_id != "NOT_SET" else "✗ NOT SET"
            },
            "actions": {
                "create_page": {
                    "description": "Create a page with automatic property type detection",
                    "required_env": ["NOTION_TOKEN", "NOTION_DB_ID"],
                    "parameters": {
                        "title": {
                            "type": "string",
                            "required": False,
                            "description": "Page title"
                        },
                        "properties": {
                            "type": "object",
                            "required": False,
                            "description": "Simple key-value properties - tool will auto-detect types"
                        }
                    },
                    "example": {
                        "title": "Mumbai Weather",
                        "properties": {
                            "Temperature": "31",
                            "Condition": "Sunny",
                            "Date": "2024-12-15"
                        }
                    },
                    "note": "Tool automatically detects property types from database schema"
                }
            }
        }

    # =========================
    # 🔹 EXECUTION
    # =========================
    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        """Execute with automatic schema detection"""
        if mode == "mock":
            return {
                "status": 200,
                "message": "Mock execution successful"
            }

        token = os.getenv("NOTION_TOKEN")
        if not token:
            return {
                "error": "NOTION_TOKEN not set",
                "status": 401
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

        try:
            if action == "create_page":
                return self._create_page_smart(headers, config)
            else:
                return {"error": f"Unknown action: {action}"}

        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            
            # Parse Notion error
            try:
                import json
                error_data = json.loads(error_text)
                message = error_data.get("message", error_text)
            except:
                message = error_text[:200]
            
            return {
                "error": f"HTTP {e.response.status_code}: {message}",
                "status": e.response.status_code,
                "suggestion": "Check database schema and property types"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": 500
            }

    # =========================
    # 🔹 SMART PAGE CREATION
    # =========================
    def _create_page_smart(self, headers: Dict, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create page with automatic property type detection"""
        
        # Get database_id
        database_id = config.get("database_id")
        if not database_id or database_id in ["YOUR_DATABASE_ID", "NOT_SET", ""]:
            database_id = os.getenv("NOTION_DB_ID")
            if not database_id:
                raise ValueError("database_id not provided and NOTION_DB_ID not set")
            print(f"   🔧 Auto-injected NOTION_DB_ID: {database_id[:8]}...")
        
        # Fetch database schema
        schema = self._get_database_schema(headers, database_id)
        if "error" in schema:
            return schema
        
        print(f"   📋 Fetched schema: {len(schema)} properties")
        
        # Translate parameters using schema
        translated = self._translate_with_schema(config, schema, database_id)
        
        print(f"   🔄 Translated {len(translated['properties'])} properties")
        
        # Create page
        url = "https://api.notion.com/v1/pages"
        
        with httpx.Client(timeout=30) as client:
            response = client.post(url, headers=headers, json=translated)
            response.raise_for_status()
            result = response.json()
            
            return {
                "status": 200,
                "data": result,
                "page_id": result.get("id"),
                "url": result.get("url"),
                "message": "✅ Page created successfully"
            }

    # =========================
    # 🔹 SCHEMA FETCHING
    # =========================
    def _get_database_schema(self, headers: Dict, database_id: str) -> Dict[str, Any]:
        """Fetch and cache database schema"""
        
        # Check cache
        if database_id in self._schema_cache:
            print(f"   💾 Using cached schema")
            return self._schema_cache[database_id]
        
        # Fetch schema
        url = f"https://api.notion.com/v1/databases/{database_id}"
        
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                
                db = response.json()
                properties = db.get("properties", {})
                
                # Cache it
                self._schema_cache[database_id] = properties
                
                return properties
                
        except Exception as e:
            return {"error": f"Failed to fetch schema: {e}"}

    # =========================
    # 🔹 SMART TRANSLATION
    # =========================
    def _translate_with_schema(
        self, 
        config: Dict[str, Any], 
        schema: Dict[str, Any],
        database_id: str
    ) -> Dict[str, Any]:
        """Translate simple params to Notion format using schema"""
        
        translated = {
            "parent": {"database_id": database_id},
            "properties": {}
        }
        
        # Handle title
        title = config.get("title", "Untitled")
        
        # Find the title property in schema
        title_prop_name = None
        for name, prop_config in schema.items():
            if prop_config.get("type") == "title":
                title_prop_name = name
                break
        
        if title_prop_name:
            translated["properties"][title_prop_name] = {
                "title": [{"text": {"content": str(title)}}]
            }
        
        # Handle other properties
        properties = config.get("properties", {})
        
        for key, value in properties.items():
            # Skip if already in Notion format
            if isinstance(value, dict) and any(k in value for k in ["title", "rich_text", "number", "select", "date"]):
                translated["properties"][key] = value
                continue
            
            # Get property type from schema
            prop_config = schema.get(key)
            if not prop_config:
                print(f"   ⚠️  Property '{key}' not in schema, using rich_text")
                translated["properties"][key] = {
                    "rich_text": [{"text": {"content": str(value)}}]
                }
                continue
            
            prop_type = prop_config.get("type")
            
            # Convert based on type
            translated_value = self._convert_value_by_type(value, prop_type, prop_config)
            
            if translated_value:
                translated["properties"][key] = translated_value
                print(f"   ✓ {key} ({prop_type}): {str(value)[:30]}")
        
        return translated

    # =========================
    # 🔹 TYPE-SPECIFIC CONVERSION
    # =========================
    def _convert_value_by_type(
        self, 
        value: Any, 
        prop_type: str,
        prop_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Convert a value based on Notion property type"""
        
        if prop_type == "rich_text":
            return {
                "rich_text": [{"text": {"content": str(value)}}]
            }
        
        elif prop_type == "number":
            # Extract number from string like "31°C" or "31"
            if isinstance(value, (int, float)):
                print(f"   → Converting number: {value}")
                return {"number": value}
            elif isinstance(value, str):
                # Try to extract number
                match = re.search(r'[-+]?\d*\.?\d+', value)
                if match:
                    num_str = match.group()
                    try:
                        num = float(num_str) if '.' in num_str else int(num_str)
                        print(f"   → Extracted number from '{value}': {num}")
                        return {"number": num}
                    except Exception as e:
                        print(f"   ⚠️  Failed to convert '{value}' to number: {e}")
                        pass
                else:
                    print(f"   ⚠️  No number found in '{value}'")
            print(f"   ⚠️  Skipping Temperature property - couldn't convert '{value}' to number")
            return None  # Skip if can't convert
        
        elif prop_type == "select":
            # Get available options
            options = prop_config.get("select", {}).get("options", [])
            option_names = [opt["name"] for opt in options]
            
            # Match value to closest option
            value_str = str(value)
            if value_str in option_names:
                return {"select": {"name": value_str}}
            
            # Try case-insensitive match
            for opt_name in option_names:
                if opt_name.lower() == value_str.lower():
                    return {"select": {"name": opt_name}}
            
            # If no match and options exist, skip
            return None
        
        elif prop_type == "multi_select":
            options = prop_config.get("multi_select", {}).get("options", [])
            option_names = [opt["name"] for opt in options]
            
            if isinstance(value, list):
                values = value
            else:
                values = [str(value)]
            
            matched = []
            for v in values:
                v_str = str(v)
                if v_str in option_names:
                    matched.append({"name": v_str})
            
            if matched:
                return {"multi_select": matched}
            return None
        
        elif prop_type == "date":
            # Try to parse date
            if isinstance(value, str):
                # Already in ISO format?
                if re.match(r'\d{4}-\d{2}-\d{2}', value):
                    return {"date": {"start": value}}
                
                # Try common formats
                try:
                    dt = datetime.strptime(value, "%Y-%m-%d")
                    return {"date": {"start": dt.strftime("%Y-%m-%d")}}
                except:
                    pass
            
            return None
        
        elif prop_type == "checkbox":
            if isinstance(value, bool):
                return {"checkbox": value}
            elif isinstance(value, str):
                return {"checkbox": value.lower() in ["true", "yes", "1"]}
            return None
        
        elif prop_type == "url":
            return {"url": str(value)}
        
        elif prop_type == "email":
            return {"email": str(value)}
        
        elif prop_type == "phone_number":
            return {"phone_number": str(value)}
        
        else:
            # Unknown type, use rich_text
            return {
                "rich_text": [{"text": {"content": str(value)}}]
            }
    
    def _create_page(self, headers, config):
        """Legacy method - now uses smart version"""
        return self._create_page_smart(headers, config)