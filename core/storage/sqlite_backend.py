import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Optional
from core.storage.base import StorageBackend
from core.schemas import WorkflowPlan, WorkflowExecution
from core.config import Config
import os

class SQLiteBackend(StorageBackend):
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.SQLITE_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    steps TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    mode TEXT DEFAULT 'real',
                    tags TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    step_results TEXT,
                    error TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
                )
            """)
            conn.commit()
    
    def save_workflow(self, plan: WorkflowPlan) -> str:
        if not plan.workflow_id:
            plan.workflow_id = str(uuid.uuid4())
        if not plan.created_at:
            plan.created_at = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO workflows 
                (workflow_id, name, description, steps, created_at, mode, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.workflow_id,
                plan.name,
                plan.description,
                json.dumps([s.model_dump() for s in plan.steps]),
                plan.created_at.isoformat(),
                plan.mode,
                json.dumps(plan.tags)
            ))
            conn.commit()
        
        return plan.workflow_id
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowPlan]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM workflows WHERE workflow_id = ?",
                (workflow_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return WorkflowPlan(
                workflow_id=row["workflow_id"],
                name=row["name"],
                description=row["description"],
                steps=json.loads(row["steps"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                mode=row["mode"],
                tags=json.loads(row["tags"])
            )
    
    def list_workflows(self, tags: Optional[List[str]] = None) -> List[WorkflowPlan]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM workflows ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            workflows = []
            for row in rows:
                workflow = WorkflowPlan(
                    workflow_id=row["workflow_id"],
                    name=row["name"],
                    description=row["description"],
                    steps=json.loads(row["steps"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    mode=row["mode"],
                    tags=json.loads(row["tags"])
                )
                
                if tags:
                    if any(tag in workflow.tags for tag in tags):
                        workflows.append(workflow)
                else:
                    workflows.append(workflow)
            
            return workflows
    
    def delete_workflow(self, workflow_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM workflows WHERE workflow_id = ?",
                (workflow_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def save_execution(self, execution: WorkflowExecution) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO executions
                (execution_id, workflow_id, status, started_at, completed_at, step_results, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                execution.execution_id,
                execution.workflow_id,
                execution.status,
                execution.started_at.isoformat(),
                execution.completed_at.isoformat() if execution.completed_at else None,
                json.dumps(execution.step_results),
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
                workflow_id=row["workflow_id"],
                status=row["status"],
                started_at=datetime.fromisoformat(row["started_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                step_results=json.loads(row["step_results"]),
                error=row["error"]
            )
