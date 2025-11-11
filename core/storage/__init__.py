from core.config import Config
from core.storage.sqlite_backend import SQLiteBackend

def get_storage():
    """Factory function to get storage backend"""
    if Config.STORAGE_TYPE == "sqlite":
        return SQLiteBackend()
    # Add more backends here (notion, postgres, etc.)
    return SQLiteBackend()  # Default
