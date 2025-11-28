# core/react_agent.py
"""
ReAct Agent for DynaFlow
Reasons about what to do, acts, observes results, and adapts
"""

from google import generativeai as genai
import os
import json
import httpx
from typing import Dict, Any, List
from datetime import datetime
import re

class ReActAgent:
    """
    ReAct (Reason + Act) Agent that can:
    1. Reason about what needs to be done
    2. Take actions (API calls, data transforms)
    3. Observe results
    4. Adapt based on what it sees
    """
    
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        self.conversation_history: List[Dict] = []
        self.max_iterations = 10
    
    def execute_workflow(self, user_goal: str) -> Dict[str, Any]:
        """
        Execute a workflow using ReAct loop
        
        Args:
            user_goal: Natural language description of what to do
            
        Returns:
            Final result with execution trace
        """
        print(f"\n{'='*70}")
        print(f"🎯 Goal: {user_goal}")
        print(f"{'='*70}\n")
        
        # Initialize conversation
        self.conversation_history = []
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            # Step 1: THINK (Reason about what to do next)
            thought = self._think(user_goal)
            print(f"💭 Thought: {thought['reasoning']}")
            
            # Check if done
            if thought['action'] == 'FINISH':
                print(f"✅ Done: {thought['final_answer']}")
                return {
                    "status": "success",
                    "result": thought['final_answer'],
                    "iterations": iteration,
                    "trace": self.conversation_history
                }
            
            # Step 2: ACT (Execute the action)
            print(f"🔧 Action: {thought['action']}")
            observation = self._act(thought)
            print(f"👁️  Observation: {str(observation)[:200]}...")
            
            # Store in history
            self.conversation_history.append({
                "iteration": iteration,
                "thought": thought,
                "observation": observation
            })
        
        return {
            "status": "max_iterations_reached",
            "result": "Could not complete task within iteration limit",
            "iterations": iteration,
            "trace": self.conversation_history
        }
    
    def _think(self, user_goal: str) -> Dict[str, Any]:
        """
        Reason about what to do next based on goal and history
        """
        # Build context from history
        history_text = self._format_history()
        
        prompt = f"""You are an AI agent that can execute workflows by calling APIs and processing data.

USER GOAL: {user_goal}

{history_text}

Available Actions:
1. API_CALL - Make an HTTP request
   Format: {{"action": "API_CALL", "method": "GET/POST/etc", "url": "...", "headers": {{}}, "body": {{}}}}

2. EXTRACT - Extract data from previous observation
   Format: {{"action": "EXTRACT", "path": "key.subkey[0].value", "from_step": <iteration_number>}}

3. TRANSFORM - Transform/format data
   Format: {{"action": "TRANSFORM", "operation": "...", "data": "..."}}

4. FINISH - Complete the task
   Format: {{"action": "FINISH", "final_answer": "..."}}

Environment Variables Available:
- OPENWEATHER_API_KEY
- NOTION_TOKEN  
- NOTION_DB_ID
- GITHUB_TOKEN

Think step by step:
1. What have I done so far?
2. What information do I have?
3. What do I need to do next?
4. Am I done?

Respond with JSON:
{{
  "reasoning": "Step by step thinking about what to do next...",
  "action": "API_CALL | EXTRACT | TRANSFORM | FINISH",
  "parameters": {{...action-specific params...}},
  "final_answer": "only if action is FINISH"
}}

Examples:

Goal: "Get Mumbai weather and add to Notion"
Thought 1: {{"reasoning": "Need to get weather data first", "action": "API_CALL", "parameters": {{"method": "GET", "url": "https://api.openweathermap.org/data/2.5/weather?q=Mumbai&appid={{{{OPENWEATHER_API_KEY}}}}&units=metric"}}}}

Observation 1: {{"main": {{"temp": 30}}, "weather": [{{"description": "clear"}}]}}

Thought 2: {{"reasoning": "I have weather data. Now need to extract temp and description, then post to Notion", "action": "API_CALL", "parameters": {{"method": "POST", "url": "https://api.notion.com/v1/pages", "headers": {{"Authorization": "Bearer {{{{NOTION_TOKEN}}}}", "Notion-Version": "2022-06-28"}}, "body": {{"parent": {{"database_id": "{{{{NOTION_DB_ID}}}}"}}, "properties": {{"Name": {{"title": [{{"text": {{"content": "Mumbai: 30°C"}}}}]}}}}}}}}}}

Observation 2: {{"id": "page-123", "url": "..."}}

Thought 3: {{"reasoning": "Successfully created Notion page. Task complete.", "action": "FINISH", "final_answer": "Created Notion page with Mumbai weather (30°C, clear sky)"}}

Now think about the user's goal:"""
        
        response = self.model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)
    
    def _act(self, thought: Dict[str, Any]) -> Any:
        """
        Execute the action and return observation
        """
        action = thought['action']
        params = thought.get('parameters', {})
        
        try:
            if action == 'API_CALL':
                return self._execute_api_call(params)
            
            elif action == 'EXTRACT':
                return self._extract_data(params)
            
            elif action == 'TRANSFORM':
                return self._transform_data(params)
            
            elif action == 'FINISH':
                return {"status": "finished"}
            
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_api_call(self, params: Dict) -> Any:
        """Execute HTTP request"""
        method = params.get('method', 'GET').upper()
        url = params.get('url', '')
        headers = params.get('headers', {})
        body = params.get('body')
        
        # Replace environment variables
        url = self._replace_env_vars(url)
        headers = self._replace_env_vars_in_dict(headers)
        body = self._replace_env_vars_in_dict(body) if body else None
        
        print(f"   → {method} {url[:80]}...")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                json=body
            )
            response.raise_for_status()
            
            try:
                return response.json()
            except:
                return {"text": response.text}
    
    def _extract_data(self, params: Dict) -> Any:
        """Extract data from previous observation"""
        path = params.get('path', '')
        from_step = params.get('from_step', len(self.conversation_history))
        
        if from_step > len(self.conversation_history):
            return {"error": "Invalid step reference"}
        
        data = self.conversation_history[from_step - 1]['observation']
        
        # Navigate path
        for part in path.split('.'):
            if '[' in part:
                # Handle array index: weather[0]
                key = part.split('[')[0]
                idx = int(part.split('[')[1].split(']')[0])
                data = data[key][idx]
            else:
                data = data[part]
        
        return data
    
    def _transform_data(self, params: Dict) -> Any:
        """Transform/format data"""
        operation = params.get('operation', '')
        data = params.get('data', '')
        
        # Simple transformations
        if operation == 'uppercase':
            return data.upper()
        elif operation == 'lowercase':
            return data.lower()
        elif operation == 'json_parse':
            return json.loads(data)
        else:
            return data
    
    def _replace_env_vars(self, text: str) -> str:
        """Replace {{VAR_NAME}} with environment variables"""
        if not isinstance(text, str):
            return text
        
        pattern = r'\{\{([A-Z_][A-Z_0-9]*)\}\}'
        
        def replacer(match):
            var_name = match.group(1)
            value = os.getenv(var_name)
            return value if value else match.group(0)
        
        return re.sub(pattern, replacer, text)
    
    def _replace_env_vars_in_dict(self, data: Any) -> Any:
        """Recursively replace env vars in dict/list"""
        if isinstance(data, dict):
            return {k: self._replace_env_vars_in_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_env_vars_in_dict(item) for item in data]
        elif isinstance(data, str):
            return self._replace_env_vars(data)
        else:
            return data
    
    def _format_history(self) -> str:
        """Format conversation history for prompt"""
        if not self.conversation_history:
            return "Previous Steps: None yet - this is the first step."
        
        lines = ["Previous Steps:"]
        for entry in self.conversation_history:
            lines.append(f"\nStep {entry['iteration']}:")
            lines.append(f"  Thought: {entry['thought']['reasoning'][:100]}...")
            lines.append(f"  Action: {entry['thought']['action']}")
            
            obs = entry['observation']
            if isinstance(obs, dict):
                obs_str = json.dumps(obs, indent=2)[:200]
            else:
                obs_str = str(obs)[:200]
            lines.append(f"  Result: {obs_str}...")
        
        return "\n".join(lines)


# API endpoint for ReAct agent
from fastapi import FastAPI
from pydantic import BaseModel

class ReActRequest(BaseModel):
    goal: str
    mode: str = "real"

def add_react_endpoint(app: FastAPI):
    """Add ReAct endpoint to existing FastAPI app"""
    
    @app.post("/react/execute")
    async def execute_react(req: ReActRequest):
        """
        Execute a workflow using ReAct agent
        
        Example:
            curl -X POST http://localhost:8000/react/execute \
              -H "Content-Type: application/json" \
              -d '{"goal": "Get Mumbai weather and add to Notion database"}'
        """
        agent = ReActAgent()
        result = agent.execute_workflow(req.goal)
        return result