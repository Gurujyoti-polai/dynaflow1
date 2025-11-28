# core/storage/base.py - SIMPLIFIED
from abc import ABC, abstractmethod
from typing import List, Optional
from core.schemas import WorkflowExecution

class StorageBackend(ABC):
    """Simplified storage - only stores execution history"""
    
    @abstractmethod
    def save_execution(self, execution: WorkflowExecution) -> str:
        """Save execution record"""
        pass
    
    @abstractmethod
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution record"""
        pass
    
    @abstractmethod
    def list_executions(self, limit: int = 10) -> List[WorkflowExecution]:
        """List recent executions"""
        pass