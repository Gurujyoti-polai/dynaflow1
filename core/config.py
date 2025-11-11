import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LLM
    GOOGLE_API_KEY = os.getenv("GEMENI_API_KEY")
    USE_REAL_LLM = bool(GOOGLE_API_KEY)
    
    # Storage
    STORAGE_TYPE = os.getenv("STORAGE_TYPE", "sqlite")  # sqlite, notion, memory
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/workflows.db")
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    NOTION_WORKFLOWS_DB_ID = os.getenv("NOTION_WORKFLOWS_DB_ID")
    
    # Execution Mode
    DEFAULT_MODE = os.getenv("DEFAULT_MODE", "real")  # real or mock
    
    # Plugins
    PLUGINS_DIR = os.getenv("PLUGINS_DIR", "./plugins")
    
    # API
    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", "8000"))