# core/storage/sqlite_backend.py - SIMPLIFIED
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from core.storage.base import StorageBackend
from core.schemas import WorkflowExecution
from core.config import Config
import os

class SQLiteBackend(StorageBackend):
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.SQLITE_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Check if old table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'"
            )
            old_table_exists = cursor.fetchone() is not None
            
            if old_table_exists:
                # Drop old tables
                print("🔄 Migrating database schema...")
                conn.execute("DROP TABLE IF EXISTS workflows")
                conn.execute("DROP TABLE IF EXISTS executions")
            
            # Create new simplified table for executions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    result TEXT,
                    iterations INTEGER DEFAULT 0,
                    trace TEXT,
                    error TEXT
                )
            """)
            conn.commit()
            
            if old_table_exists:
                print("✅ Database migrated to new schema")
    
    def save_execution(self, execution: WorkflowExecution) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO executions
                (execution_id, goal, status, started_at, completed_at, result, iterations, trace, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                execution.execution_id,
                execution.goal,
                execution.status,
                execution.started_at.isoformat(),
                execution.completed_at.isoformat() if execution.completed_at else None,
                json.dumps(execution.result) if execution.result else None,
                execution.iterations,
                json.dumps(execution.trace) if execution.trace else None,
                execution.error
            ))
            conn.commit()
        
        return execution.execution_id
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM executions WHERE execution_id = ?",
                (execution_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return WorkflowExecution(
                execution_id=row["execution_id"],
                goal=row["goal"],
                status=row["status"],
                started_at=datetime.fromisoformat(row["started_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                result=json.loads(row["result"]) if row["result"] else None,
                iterations=row["iterations"],
                trace=json.loads(row["trace"]) if row["trace"] else [],
                error=row["error"]
            )
    
    def list_executions(self, limit: int = 10) -> List[WorkflowExecution]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM executions ORDER BY started_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            
            executions = []
            for row in rows:
                executions.append(WorkflowExecution(
                    execution_id=row["execution_id"],
                    goal=row["goal"],
                    status=row["status"],
                    started_at=datetime.fromisoformat(row["started_at"]),
                    completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    result=json.loads(row["result"]) if row["result"] else None,
                    iterations=row["iterations"],
                    trace=json.loads(row["trace"]) if row["trace"] else [],
                    error=row["error"]
                ))
            
            return executions