# tools/integrations/gmail.py

from typing import Dict, Any
import os
import base64
import pickle

from email.mime.text import MIMEText

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from tools.base import ToolBase


class GmailTool(ToolBase):
    """
    Gmail integration using OAuth
    Supports sending emails
    """

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    # -------------------------
    # Tool identity
    # -------------------------
    @property
    def name(self) -> str:
        return "gmail"

    @property
    def description(self) -> str:
        return "Send emails using Gmail OAuth"

    @property
    def category(self) -> str:
        return "integration"

    # -------------------------
    # Schema for LLM (QUERY_TOOL)
    # -------------------------
    def get_schema(self) -> Dict[str, Any]:
        creds_path = os.getenv("GMAIL_CREDENTIALS_PATH", "NOT_SET")
        token_path = os.getenv("GMAIL_TOKEN_PATH", "NOT_SET")

        return {
            "tool": self.name,
            "description": self.description,
            "environment": {
                "GMAIL_CREDENTIALS_PATH": (
                    f"✓ Set ({creds_path})" if creds_path != "NOT_SET" else "✗ NOT SET"
                ),
                "GMAIL_TOKEN_PATH": (
                    f"✓ Set ({token_path})" if token_path != "NOT_SET" else "✗ NOT SET"
                )
            },
            "actions": {
                "send_email": {
                    "description": "Send an email using Gmail",
                    "required_env": [
                        "GMAIL_CREDENTIALS_PATH",
                        "GMAIL_TOKEN_PATH"
                    ],
                    "parameters": {
                        "to": {
                            "type": "string",
                            "required": True,
                            "description": "Recipient email address"
                        },
                        "subject": {
                            "type": "string",
                            "required": True,
                            "description": "Email subject"
                        },
                        "body": {
                            "type": "string",
                            "required": True,
                            "description": "Plain text email body"
                        }
                    },
                    "example": {
                        "to": "user@example.com",
                        "subject": "Test Email",
                        "body": "Hello from DynaFlow"
                    }
                }
            }
        }

    # -------------------------
    # Runtime execution
    # -------------------------
    def execute(
        self,
        action: str,
        config: Dict[str, Any],
        mode: str = "real"
    ) -> Dict[str, Any]:

        if mode == "mock":
            return {
                "status": 200,
                "message": "Mock Gmail execution successful"
            }

        if action != "send_email":
            return {
                "error": f"Unknown action: {action}",
                "status": 400
            }

        # Validate env
        creds_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        token_path = os.getenv("GMAIL_TOKEN_PATH")

        if not creds_path or not token_path:
            return {
                "error": "GMAIL_CREDENTIALS_PATH or GMAIL_TOKEN_PATH not set",
                "status": 401
            }

        try:
            service = self._get_gmail_service(creds_path, token_path)

            to = config.get("to")
            subject = config.get("subject")
            body = config.get("body")

            if not to or not subject or not body:
                return {
                    "error": "Missing required parameters: to, subject, body",
                    "status": 400
                }

            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject

            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode()

            sent = (
                service.users()
                .messages()
                .send(
                    userId="me",
                    body={"raw": raw_message}
                )
                .execute()
            )

            return {
                "status": 200,
                "message": "✅ Email sent successfully",
                "id": sent.get("id"),
                "thread_id": sent.get("threadId")
            }

        except Exception as e:
            return {
                "error": str(e),
                "status": 500
            }

    # -------------------------
    # Internal helpers
    # -------------------------
    def _get_gmail_service(self, creds_path: str, token_path: str):
        creds = None

        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    creds_path,
                    self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        return build("gmail", "v1", credentials=creds)
