from typing import Dict, Any
from core.schemas import WorkflowPlan

def generate_mermaid(plan: WorkflowPlan) -> str:
    """Generate Mermaid diagram from workflow plan"""
    lines = ["graph TD"]
    lines.append(f'    START["{plan.name}"]')
    
    for step in plan.steps:
        step_label = f"{step.step_id}[\"{step.description}\"]"
        lines.append(f"    {step_label}")
        
        # Add connections
        if step.depends_on:
            for dep in step.depends_on:
                lines.append(f"    {dep} --> {step.step_id}")
        else:
            lines.append(f"    START --> {step.step_id}")
    
    return "\n".join(lines)

def generate_ascii_flow(plan: WorkflowPlan) -> str:
    """Generate ASCII art workflow visualization"""
    output = []
    output.append("=" * 60)
    output.append(f"WORKFLOW: {plan.name}")
    output.append(f"MODE: {plan.mode.upper()}")
    output.append("=" * 60)
    
    for idx, step in enumerate(plan.steps, 1):
        prefix = "└──" if idx == len(plan.steps) else "├──"
        output.append(f"\n{prefix} Step {idx}: {step.step_id}")
        output.append(f"    Type: {step.step_type}")
        output.append(f"    Desc: {step.description}")
        if step.depends_on:
            output.append(f"    Deps: {', '.join(step.depends_on)}")
    
    output.append("\n" + "=" * 60)
    return "\n".join(output)
