# core/storage/__init__.py - SIMPLIFIED
from core.config import Config
from core.storage.sqlite_backend import SQLiteBackend

def get_storage():
    """Factory function to get storage backend"""
    # For now, only SQLite
    # Can add more backends later if needed
    return SQLiteBackend()