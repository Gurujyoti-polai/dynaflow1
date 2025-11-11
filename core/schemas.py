from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime

class ActionStep(BaseModel):
    step_id: str
    step_type: Literal["http_request", "transform", "condition", "loop", "wait", "plugin", "custom"]
    description: str
    config: Dict[str, Any] = Field(default_factory=dict)
    depends_on: Optional[List[str]] = None
    plugin_name: Optional[str] = None  # For plugin steps

class WorkflowPlan(BaseModel):
    workflow_id: Optional[str] = None
    name: str
    description: str
    steps: List[ActionStep]
    created_at: Optional[datetime] = None
    mode: Literal["real", "mock"] = "real"
    tags: List[str] = Field(default_factory=list)

class WorkflowExecution(BaseModel):
    execution_id: str
    workflow_id: str
    status: Literal["running", "success", "failed"]
    started_at: datetime
    completed_at: Optional[datetime] = None
    step_results: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None