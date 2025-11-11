from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any, Annotated
from core.schemas import WorkflowPlan, ActionStep, WorkflowExecution
from core.plugins.registry import plugin_registry
from datetime import datetime
import httpx
import uuid
import os
import re
from operator import add

class WorkflowState(TypedDict):
    step_results: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
    error: str | None

def replace_env_vars(text: str) -> str:
    if not isinstance(text, str):
        return text
    
    original_text = text
    
    def replace_your_pattern(match):
        full_match = match.group(0)
        var_name = match.group(1)
        env_value = os.getenv(var_name)
        
        if not env_value:
            variations = [
                var_name.replace("_API_KEY", "_KEY"),
                var_name.replace("_API_TOKEN", "_TOKEN"),
                var_name.replace("_DATABASE_ID", "_DB_ID"),
                var_name.replace("_DB_ID", "_DATABASE_ID"),
                var_name.replace("_TOKEN", "_API_TOKEN"),
                var_name.replace("_KEY", "_API_KEY"),
            ]
            for variant in variations:
                env_value = os.getenv(variant)
                if env_value:
                    print(f"🔑 Replaced {full_match} with {variant} (variant)")
                    return env_value
        
        if env_value:
            print(f"🔑 Replaced {full_match} with {var_name}")
            return env_value
        
        print(f"⚠️  Warning: {var_name} not found")
        return full_match
    
    text = re.sub(r'YOUR_([A-Z_0-9]+)', replace_your_pattern, text)
    
    def replace_env_curly_pattern(match):
        var_name = match.group(1)
        if re.match(r'^[A-Z_0-9]+$', var_name):
            env_value = os.getenv(var_name)
            
            if not env_value:
                variations = [
                    var_name.replace("_API_KEY", "_KEY"),
                    var_name.replace("_API_TOKEN", "_TOKEN"),
                    var_name.replace("_DATABASE_ID", "_DB_ID"),
                    var_name.replace("_DB_ID", "_DATABASE_ID"),
                    var_name.replace("_TOKEN", "_API_TOKEN"),
                    var_name.replace("_KEY", "_API_KEY"),
                ]
                for variant in variations:
                    env_value = os.getenv(variant)
                    if env_value:
                        print(f"🔑 Replaced {{{{{var_name}}}}} with {variant} (variant)")
                        return env_value
            
            if env_value:
                print(f"🔑 Replaced {{{{{var_name}}}}}")
                return env_value
            print(f"⚠️  Warning: {var_name} not found")
        return match.group(0)
    
    text = re.sub(r'\{\{([A-Z_][A-Z_0-9]*)\}\}', replace_env_curly_pattern, text)
    
    if text != original_text:
        print(f"   Original: {original_text[:100]}...")
        print(f"   Replaced: {text[:100]}...")
    
    return text

def replace_env_vars_in_dict(data):
    if isinstance(data, dict):
        return {k: replace_env_vars_in_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_env_vars_in_dict(item) for item in data]
    elif isinstance(data, str):
        return replace_env_vars(data)
    else:
        return data

def replace_template_vars(text: str, state: WorkflowState) -> str:
    if not isinstance(text, str):
        return text
    
    text = text.replace("{{NOW()}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    text = text.replace("{{CURRENT_DATE_TIME}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    text = text.replace("{{CURRENT_DATE}}", datetime.now().strftime("%Y-%m-%d"))
    
    pattern = r'\{\{([^}]+)\}\}'
    matches = re.findall(pattern, text)
    
    for match in matches:
        if match in ["NOW()", "CURRENT_DATE_TIME", "CURRENT_DATE"]:
            continue
        if re.match(r'^[A-Z_][A-Z_0-9]*$', match):
            continue
            
        parts = match.strip().split('.')
        value = state["step_results"]
        
        try:
            for part in parts:
                if part.startswith('[') and part.endswith(']'):
                    idx = int(part[1:-1])
                    value = value[idx]
                else:
                    value = value.get(part, match) if isinstance(value, dict) else value
            
            text = text.replace(f"{{{{{match}}}}}", str(value))
        except Exception as e:
            print(f"   Warning: Could not resolve {{{{{match}}}}}: {e}")
    
    return text

def replace_template_vars_in_dict(data, state: WorkflowState):
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            replaced_value = replace_template_vars_in_dict(v, state)
            # Skip keys with unresolved placeholders that look like UUIDs
            if isinstance(replaced_value, str) and "YOUR_" in replaced_value:
                continue  # Don't include unresolved env vars
            result[k] = replaced_value
        return result
    elif isinstance(data, list):
        return [replace_template_vars_in_dict(item, state) for item in data]
    elif isinstance(data, str):
        result = replace_template_vars(data, state)
        if result.replace('.', '').replace('-', '').isdigit():
            try:
                if '.' in result:
                    return float(result)
                else:
                    return int(result)
            except:
                pass
        return result
    else:
        return data

def execute_plugin_step(step: ActionStep, state: WorkflowState, mode: str):
    plugin = plugin_registry.get(step.plugin_name)
    if not plugin:
        return {"error": f"Plugin '{step.plugin_name}' not found"}
    action = step.config.get("action")
    return plugin.execute(action, step.config, mode)

def execute_http_request(step: ActionStep, state: WorkflowState, mode: str):
    config = step.config
    
    if mode == "mock":
        return {"status": 200, "mock": True, "message": f"Mock: {config.get('method', 'GET')} {config.get('url')}"}
    
    print(f"\n🔍 Before env var replacement:")
    print(f"   URL: {config.get('url', '')[:100]}")
    
    config = replace_env_vars_in_dict(config)
    
    print(f"\n🔍 After env var replacement:")
    print(f"   URL: {config.get('url', '')[:100]}")
    
    method = config.get("method", "GET").upper()
    url = config.get("url")
    headers = config.get("headers", {})
    body = config.get("body")
    params = config.get("params", {})
    
    url = replace_template_vars(url, state)
    headers = replace_template_vars_in_dict(headers, state)
    body = replace_template_vars_in_dict(body, state)
    params = replace_template_vars_in_dict(params, state)
    
    print(f"🌐 HTTP {method} {url}")
    
    try:
        with httpx.Client(timeout=30.0) as client:
            if method == "GET":
                response = client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = client.post(url, headers=headers, json=body, params=params)
            elif method == "PUT":
                response = client.put(url, headers=headers, json=body, params=params)
            elif method == "DELETE":
                response = client.delete(url, headers=headers, params=params)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            response.raise_for_status()
            
            try:
                data = response.json()
            except:
                data = response.text
            
            return {"status": response.status_code, "data": data, "result": data}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def execute_transform(step: ActionStep, state: WorkflowState, mode: str):
    config = step.config
    operation = config.get("operation")
    
    if mode == "mock":
        return {"status": "success", "mock": True, "operation": operation, "result": "Mock data"}
    
    source = config.get("source")
    if source and source in state["step_results"]:
        source_data = state["step_results"][source]
    else:
        source_data = {}
    
    try:
        if operation == "template":
            template = config.get("template", "")
            result = replace_template_vars(template, state)
            return {"status": "success", "result": result}
        
        elif operation in ["extract_json_path", "get_field"]:
            # Handle both 'path' and 'field' config keys
            path = config.get("path") or config.get("field", "")
            value = source_data
            
            print(f"   Source: {list(source_data.keys()) if isinstance(source_data, dict) else type(source_data)}")
            
            if isinstance(source_data, dict):
                if "result" in source_data and isinstance(source_data["result"], dict):
                    value = source_data["result"]
                    print(f"   Using 'result' wrapper")
                elif "data" in source_data and isinstance(source_data["data"], dict):
                    value = source_data["data"]
                    print(f"   Using 'data' wrapper")
            
            for part in path.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                    if value is None:
                        print(f"   ⚠️  '{part}' not found")
                        break
                    print(f"   Found: {part} = {value}")
                else:
                    value = None
                    break
            
            print(f"   Final: {path} = {value}")
            return {"status": "success", "result": value}
        
        return {"status": "success", "result": source_data}
    
    except Exception as e:
        return {"error": f"Transform error: {str(e)}"}

def execute_condition(step: ActionStep, state: WorkflowState, mode: str):
    config = step.config
    
    if mode == "mock":
        return {"status": "success", "mock": True, "condition_met": True}
    
    try:
        left = config.get("left")
        operator = config.get("operator", "==")
        right = config.get("right")
        
        if isinstance(left, str):
            left = replace_template_vars(left, state)
        
        result = False
        if operator == "==":
            result = left == right
        elif operator == "!=":
            result = left != right
        elif operator == ">":
            result = float(left) > float(right)
        elif operator == "<":
            result = float(left) < float(right)
        
        return {"status": "success", "condition_met": result}
    except Exception as e:
        return {"error": f"Condition error: {str(e)}"}

def execute_loop(step: ActionStep, state: WorkflowState, mode: str):
    config = step.config
    
    if mode == "mock":
        return {"status": "success", "mock": True, "iterations": 5}
    
    try:
        source = config.get("source")
        items = []
        
        if source and source in state["step_results"]:
            source_data = state["step_results"][source]
            items = source_data.get("result", []) if isinstance(source_data, dict) else source_data
        
        if not isinstance(items, list):
            items = [items]
        
        results = [{"item": item, "processed": True} for item in items]
        return {"status": "success", "iterations": len(results), "results": results}
    except Exception as e:
        return {"error": f"Loop error: {str(e)}"}

def execute_step(step: ActionStep, state: WorkflowState, mode: str):
    if step.step_type == "plugin":
        return execute_plugin_step(step, state, mode)
    elif step.step_type == "http_request":
        return execute_http_request(step, state, mode)
    elif step.step_type == "transform":
        return execute_transform(step, state, mode)
    elif step.step_type == "condition":
        return execute_condition(step, state, mode)
    elif step.step_type == "loop":
        return execute_loop(step, state, mode)
    elif step.step_type == "wait":
        if mode == "mock":
            return {"status": "mock_wait", "seconds": step.config.get("seconds", 1)}
        import time
        seconds = step.config.get("seconds", 1)
        time.sleep(seconds)
        return {"status": "waited", "seconds": seconds}
    elif step.step_type == "custom":
        if mode == "mock":
            return {"status": "success", "mock": True, "custom": step.config}
        return {"status": "success", "config": step.config}
    else:
        return {"error": f"Unknown step type: {step.step_type}"}

def build_and_run(plan: WorkflowPlan) -> WorkflowExecution:
    execution = WorkflowExecution(
        execution_id=str(uuid.uuid4()),
        workflow_id=plan.workflow_id or "adhoc",
        status="running",
        started_at=datetime.now()
    )
    
    graph = StateGraph(WorkflowState)
    
    def start_node(s: WorkflowState) -> WorkflowState:
        return {"step_results": {}, "error": None}
    
    graph.add_node("start", start_node)
    graph.set_entry_point("start")
    last_node = "start"
    
    for step in plan.steps:
        node_id = step.step_id
        
        def make_node(current_step):
            def node(state: WorkflowState) -> dict:
                if state.get("error"):
                    return {"step_results": {}}
                
                print(f"\n▶️  {current_step.step_id}: {current_step.description}")
                result = execute_step(current_step, state, plan.mode)
                
                if isinstance(result, dict) and result.get("error"):
                    return {
                        "step_results": {},
                        "error": f"{current_step.step_id}: {result['error']}"
                    }
                
                # Return the new step result to be merged with existing results
                return {"step_results": {current_step.step_id: result}}
            
            return node
        
        graph.add_node(node_id, make_node(step))
        
        if step.depends_on:
            for dep in step.depends_on:
                graph.add_edge(dep, node_id)
        else:
            graph.add_edge(last_node, node_id)
        
        last_node = node_id
    
    graph.add_edge(last_node, END)
    workflow = graph.compile()
    
    final_state = workflow.invoke({"step_results": {}, "error": None})
    
    execution.completed_at = datetime.now()
    execution.step_results = final_state.get("step_results", {})
    execution.error = final_state.get("error")
    execution.status = "success" if not execution.error else "failed"
    
    return execution