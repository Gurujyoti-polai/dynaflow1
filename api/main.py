# api/main.py - SIMPLIFIED VERSION
"""
DynaFlow API - ReAct Agent Only
Clean, simple, powerful
"""

from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from core.react_agent import ReActAgent
from core.storage import get_storage
from core.config import Config
import logging
from datetime import datetime
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dynaflow")

# Initialize
storage = get_storage()
app = FastAPI(
    title="DynaFlow - AI Workflow Automation",
    description="Turn natural language into automated workflows using ReAct agent"
)

class WorkflowRequest(BaseModel):
    goal: str  # Natural language goal
    save: bool = False  # Save execution history

class WorkflowResponse(BaseModel):
    execution_id: str
    status: str
    result: Any  # Changed from 'any' to 'Any'
    iterations: int
    trace: List[Dict[str, Any]]  # Changed from 'list' to 'List[Dict[str, Any]]'
    error: Optional[str] = None

@app.get("/")
async def root():
    return {
        "name": "DynaFlow",
        "version": "2.0 (ReAct)",
        "description": "AI-powered workflow automation using ReAct agent",
        "features": [
            "✅ Natural language to workflows",
            "✅ Self-correcting execution",
            "✅ Adaptive decision making",
            "✅ No manual plugin coding needed"
        ],
        "endpoints": {
            "/execute": "Execute a workflow from natural language",
            "/executions/{id}": "Get execution history",
            "/health": "Health check"
        }
    }

@app.post("/execute", response_model=WorkflowResponse)
async def execute_workflow(req: WorkflowRequest):
    """
    Execute a workflow using ReAct agent
    
    Example:
        {
          "goal": "Get Mumbai weather and add to my Notion database",
          "save": true
        }
    """
    execution_id = str(uuid.uuid4())
    
    try:
        logger.info(f"🎯 Executing: {req.goal}")
        
        # Create agent and execute
        agent = ReActAgent()
        result = agent.execute_workflow(req.goal)
        
        # Build response
        response = WorkflowResponse(
            execution_id=execution_id,
            status=result['status'],
            result=result.get('result'),
            iterations=result.get('iterations', 0),
            trace=result.get('trace', []),
            error=result.get('error')
        )
        
        # Save if requested
        if req.save:
            from core.schemas import WorkflowExecution
            execution_record = WorkflowExecution(
                execution_id=execution_id,
                goal=req.goal,
                status=result['status'],
                started_at=datetime.now(),
                completed_at=datetime.now(),
                result=result.get('result'),
                iterations=result.get('iterations', 0),
                trace=result.get('trace', []),
                error=result.get('error')
            )
            storage.save_execution(execution_record)
            logger.info(f"💾 Saved execution: {execution_id}")
        
        return response
    
    except Exception as e:
        logger.exception("Error executing workflow")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution history by ID"""
    execution = storage.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution

@app.get("/executions")
async def list_executions(limit: int = 10):
    """List recent executions"""
    executions = storage.list_executions(limit)
    return {"executions": executions, "count": len(executions)}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "gemini_api_key": "✓" if Config.GOOGLE_API_KEY else "✗",
            "storage": Config.STORAGE_TYPE
        }
    }

# Optional: Keep backward compatibility
@app.post("/react/execute")
async def execute_react_legacy(req: WorkflowRequest):
    """Legacy endpoint - redirects to /execute"""
    return await execute_workflow(req)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT)