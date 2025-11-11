from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from core.planner import parse_prompt_to_plan
from core.executor import build_and_run
from core.storage import get_storage
from core.plugins.registry import plugin_registry
from core.visualizer import generate_mermaid, generate_ascii_flow
from core.config import Config
from core.schemas import WorkflowPlan
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dynaflow")

# Initialize
storage = get_storage()
plugin_registry.load_from_directory(Config.PLUGINS_DIR)

app = FastAPI(title="DynaFlow Phase 2 - Universal Workflow Engine")

class ExecRequest(BaseModel):
    prompt: str
    mode: Optional[str] = None  # real or mock
    save: bool = False

class RunWorkflowRequest(BaseModel):
    workflow_id: str
    mode: Optional[str] = None

@app.get("/")
async def root():
    return {
        "message": "DynaFlow Phase 2",
        "features": [
            "✅ Mock/Real mode toggling",
            "✅ Persistent storage (SQLite)",
            "✅ Visual flow diagrams",
            "✅ Dynamic plugin loading"
        ],
        "plugins": list(plugin_registry.list_plugins().keys())
    }

@app.post("/execute")
async def execute(req: ExecRequest):
    try:
        logger.info(f"📝 Prompt: {req.prompt}")
        
        plan = parse_prompt_to_plan(req.prompt)
        plan.mode = req.mode or Config.DEFAULT_MODE
        
        if req.save:
            workflow_id = storage.save_workflow(plan)
            plan.workflow_id = workflow_id
            logger.info(f"💾 Saved workflow: {workflow_id}")
        
        execution = build_and_run(plan)
        
        if execution.workflow_id != "adhoc":
            storage.save_execution(execution)
        
        return {
            "status": execution.status,
            "execution_id": execution.execution_id,
            "workflow_id": plan.workflow_id,
            "mode": plan.mode,
            "plan": plan.model_dump(),
            "result": execution.step_results,
            "error": execution.error
        }
    
    except Exception as e:
        logger.exception("Error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflows")
async def list_workflows(tags: Optional[str] = None):
    tag_list = tags.split(",") if tags else None
    workflows = storage.list_workflows(tag_list)
    return {"workflows": [w.model_dump() for w in workflows]}

@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = storage.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow.model_dump()

@app.post("/workflows/{workflow_id}/run")
async def run_saved_workflow(workflow_id: str, req: RunWorkflowRequest):
    workflow = storage.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow.mode = req.mode or workflow.mode
    execution = build_and_run(workflow)
    storage.save_execution(execution)
    
    return {
        "status": execution.status,
        "execution_id": execution.execution_id,
        "result": execution.step_results,
        "error": execution.error
    }

@app.get("/workflows/{workflow_id}/visualize")
async def visualize_workflow(workflow_id: str, format: str = "ascii"):
    workflow = storage.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    if format == "mermaid":
        return {"diagram": generate_mermaid(workflow)}
    else:
        return {"diagram": generate_ascii_flow(workflow)}

@app.get("/workflows/{workflow_id}/diagram", response_class=HTMLResponse)
async def workflow_diagram(workflow_id: str):
    workflow = storage.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    mermaid_code = generate_mermaid(workflow)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{workflow.name} - Flow Diagram</title>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    </head>
    <body>
        <h1>{workflow.name}</h1>
        <p>{workflow.description}</p>
        <div class="mermaid">
        {mermaid_code}
        </div>
        <script>mermaid.initialize({{startOnLoad:true}});</script>
    </body>
    </html>
    """
    return html

@app.get("/plugins")
async def list_plugins():
    return plugin_registry.list_plugins()

@app.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    execution = storage.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution.model_dump()

@app.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    success = storage.delete_workflow(workflow_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"status": "deleted"}