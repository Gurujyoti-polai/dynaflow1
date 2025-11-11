from abc import ABC, abstractmethod
from typing import List, Optional
from core.schemas import WorkflowPlan, WorkflowExecution

class StorageBackend(ABC):
    @abstractmethod
    def save_workflow(self, plan: WorkflowPlan) -> str:
        """Save workflow and return workflow_id"""
        pass
    
    @abstractmethod
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowPlan]:
        """Retrieve workflow by ID"""
        pass
    
    @abstractmethod
    def list_workflows(self, tags: Optional[List[str]] = None) -> List[WorkflowPlan]:
        """List all workflows, optionally filtered by tags"""
        pass
    
    @abstractmethod
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete workflow"""
        pass
    
    @abstractmethod
    def save_execution(self, execution: WorkflowExecution) -> str:
        """Save execution record"""
        pass
    
    @abstractmethod
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution record"""
        pass
