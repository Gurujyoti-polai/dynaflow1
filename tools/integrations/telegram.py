# tools/telegram.py

import os
import requests
from typing import Dict, Any

class TelegramTool:
    name = "telegram"
    description = "Send messages via Telegram bot"
    category = "communication"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "description": self.description,
            "environment": {
                "TELEGRAM_BOT_TOKEN": "✓ Set" if os.getenv("TELEGRAM_BOT_TOKEN") else "✗ NOT SET",
                "TELEGRAM_CHAT_ID": "✓ Set" if os.getenv("TELEGRAM_CHAT_ID") else "✗ NOT SET",
            },
            "actions": {
                "send_message": {
                    "description": "Send a Telegram message",
                    "required_env": [
                        "TELEGRAM_BOT_TOKEN",
                        "TELEGRAM_CHAT_ID"
                    ],
                    "parameters": {
                        "text": {
                            "type": "string",
                            "required": True,
                            "description": "Message text to send"
                        }
                    }
                }
            }
        }

    def execute(self, action: str, parameters: Dict[str, Any], mode="real") -> Dict[str, Any]:
        if action != "send_message":
            return {"error": f"Unsupported action: {action}"}

        text = parameters.get("text")
        if not text:
            return {"error": "Missing required parameter: text"}

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            return {"error": "Telegram credentials not configured"}

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()

            if not data.get("ok"):
                return {
                    "status": resp.status_code,
                    "error": data
                }

            return {
                "status": 200,
                "ok": True,
                "message_id": data["result"]["message_id"]
            }

        except Exception as e:
            return {"error": str(e)}
