# core/schemas.py - SIMPLIFIED
"""
Minimal schemas for ReAct-based DynaFlow
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime

class WorkflowExecution(BaseModel):
    """Record of a workflow execution"""
    execution_id: str
    goal: str
    status: str  # "success", "failed", "max_iterations"
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    iterations: int = 0
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

# That's it! No need for ActionStep, WorkflowPlan, etc.
# ReAct agent handles everything dynamically