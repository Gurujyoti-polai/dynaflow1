"""
ReAct Agent with Dynamic Tool System
"""

from openai import OpenAI
import os
import json
import re
from typing import Dict, Any, List

# Import the tool registry
from tools import registry


class ReActAgent:
    """
    ReAct Agent with dynamic tool discovery and fallback
    """
    
    def __init__(self):
        # Use Ollama
        self.client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        )
        self.model = "llama3.1:8b"
        print("🤖 Using Ollama (Local)")
        
        # Tool system
        self.tools = registry
        self.conversation_history: List[Dict] = []
        self.max_iterations = 12
    
    def execute_workflow(self, user_goal: str) -> Dict[str, Any]:
        """
        Execute a workflow using ReAct loop with tools
        """
        print(f"\n{'='*70}")
        print(f"🎯 Goal: {user_goal}")
        print(f"{'='*70}\n")
        
        self.conversation_history = []
        iteration = 0
        repeated_actions = {}  # Track repeated actions
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            # THINK
            thought = self._think(user_goal)
            print(f"💭 Thought: {thought['reasoning'][:150]}...")
            
            # Check for repeated actions
            action_key = f"{thought.get('action')}:{thought.get('tool')}:{thought.get('tool_action')}"
            repeated_actions[action_key] = repeated_actions.get(action_key, 0) + 1
            
            if repeated_actions[action_key] > 2:
                print(f"⚠️  Action repeated {repeated_actions[action_key]} times. Auto-finishing.")
                return {
                    "status": "success",
                    "result": self._extract_final_answer(),
                    "iterations": iteration,
                    "trace": self.conversation_history
                }
            
            # Check if done
            if thought['action'] == 'FINISH':
                print(f"✅ Done: {thought['final_answer']}")
                return {
                    "status": "success",
                    "result": thought['final_answer'],
                    "iterations": iteration,
                    "trace": self.conversation_history
                }
            
            # ACT
            print(f"🔧 Action: {thought['action']}")
            observation = self._act(thought)
            
            # Handle errors
            if isinstance(observation, dict):
                if "error" in observation:
                    print(f"❌ Error: {observation['error'][:100]}...")
                    if "fallback_suggestion" in observation:
                        print(f"💡 Suggestion: {observation['fallback_suggestion']}")
                elif "number" in observation and "html_url" in observation:
                    # GitHub issue created successfully
                    print(f"✅✅✅ SUCCESS! GitHub issue created: #{observation.get('number')}")
                    print(f"🔗 URL: {observation.get('html_url')}")
                elif observation.get("status") == 200:
                    print(f"✅ HTTP 200 - Success")
                elif observation.get("status") >= 400:
                    print(f"⚠️  HTTP {observation.get('status')} error")
                else:
                    print(f"👁️  Observation: {str(observation)[:200]}...")
            else:
                print(f"👁️  Observation: {str(observation)[:200]}...")
            
            # Store in history
            self.conversation_history.append({
                "iteration": iteration,
                "thought": thought,
                "observation": observation
            })
        
        return {
            "status": "max_iterations_reached",
            "result": self._extract_final_answer(),
            "iterations": iteration,
            "trace": self.conversation_history
        }
    
    def _clean_json_response(self, text: str) -> str:
        """
        Clean LLM response to extract valid JSON
        """
        print(f"🧼 Cleaning input ({len(text)} chars)...")
        
        # Remove markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
            print("   Removed ```json``` wrapper")
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            print("   Removed ``` wrapper")
        
        # Find JSON object boundaries
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        print(f"   JSON boundaries: start={start_idx}, end={end_idx}")
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON object found in response")
        
        text = text[start_idx:end_idx+1]
        print(f"   Extracted JSON object ({len(text)} chars)")
        
        # Remove trailing commas before closing braces/brackets
        original_len = len(text)
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        if len(text) != original_len:
            print(f"   Removed trailing commas")
        
        result = text.strip()
        print(f"   Final cleaned ({len(result)} chars)")
        return result
    
    def _think(self, user_goal: str) -> Dict[str, Any]:
        """
        Agent reasons about what to do next - GENERIC VERSION
        """
        history_text = self._format_history()
        tool_manifest = self.tools.list_manifest()
        
        # Get GitHub token status
        github_token = os.environ.get('GITHUB_TOKEN', '')
        
        # Check what has been accomplished
        task_completed = False
        github_issue_created = False
        last_result = None
        
        for entry in self.conversation_history:
            obs = entry.get('observation', {})
            
            if isinstance(obs, dict):
                # Check if GitHub issue was created
                if 'number' in obs and 'html_url' in obs and 'dynaflow' in str(obs.get('html_url', '')):
                    github_issue_created = True
                    task_completed = True
                    last_result = obs
                
                # Check for errors
                if 'error' in obs:
                    last_result = obs
        
        prompt = f"""You are an AI agent that executes workflows. You must respond with ONLY valid JSON.

USER GOAL: {user_goal}

{history_text}

Available Tools:
{tool_manifest}

ENVIRONMENT STATUS:
- GitHub Token: {"✓ CONFIGURED" if github_token else "✗ MISSING"}

TASK ANALYSIS:
Goal mentions: {"GitHub" if "github" in user_goal.lower() else "Weather" if "weather" in user_goal.lower() else "Notion" if "notion" in user_goal.lower() else "Unknown"}
Task completed: {"YES - FINISH NOW!" if task_completed else "NO - Continue"}
GitHub issue created: {"YES" if github_issue_created else "NO"}

🎯 DECISION LOGIC:

1. If task is ALREADY COMPLETED (check Previous Steps):
   → Use FINISH action with success message

2. If goal mentions "GitHub" AND "issue":
   → Use github tool with create_issue action
   → Extract repo name from goal (format: owner/repo)
   → Extract issue title and body from goal

3. If goal mentions "weather":
   → Use http tool to GET weather data
   → Then decide next step based on goal

4. If goal mentions "notion":
   → Use notion tool or http POST to Notion API

5. Otherwise:
   → Analyze goal and choose appropriate tool

RESPONSE FORMATS:

Format 1 - FINISH (task completed):
{{
  "reasoning": "GitHub issue was created successfully in previous step",
  "action": "FINISH",
  "final_answer": "Successfully created GitHub issue #{last_result.get('number') if last_result and 'number' in last_result else 'N/A'} at {last_result.get('html_url') if last_result and 'html_url' in last_result else 'unknown'}"
}}

Format 2 - Create GitHub Issue:
{{
  "reasoning": "creating GitHub issue as requested in goal",
  "action": "USE_TOOL",
  "tool": "github",
  "tool_action": "create_issue",
  "parameters": {{
    "repo": "owner/repository",
    "title": "Issue title from goal",
    "body": "Issue description from goal"
  }}
}}

Format 3 - Get Weather:
{{
  "reasoning": "fetching weather data for city",
  "action": "USE_TOOL",
  "tool": "http",
  "tool_action": "GET",
  "parameters": {{
    "url": "https://wttr.in/CityName?format=j1"
  }}
}}

⚠️ CRITICAL RULES:
- ALWAYS check "Previous Steps" first
- If you see GitHub issue already created → FINISH immediately
- NEVER repeat the same action twice
- Use the tool that matches the goal (github for GitHub, http for APIs, etc.)

NOW ANALYZE THE GOAL AND RESPOND:"""
        
        response_text = ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON-only AI agent. Always respond with valid JSON only. Never add explanations, markdown, or any text outside the JSON object."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content.strip()
            print(f"🔍 Raw response ({len(response_text)} chars):\n{response_text}\n")
            
            # Clean the JSON response
            cleaned_text = self._clean_json_response(response_text)
            print(f"🧹 Cleaned JSON ({len(cleaned_text)} chars):\n{cleaned_text}\n")
            
            # Parse JSON
            thought = json.loads(cleaned_text)
            print(f"✅ Parsed successfully: action={thought.get('action')}, tool={thought.get('tool')}\n")
            
            # Validate required fields
            if "action" not in thought:
                raise ValueError("Missing 'action' field in response")
            
            if thought["action"] not in ["USE_TOOL", "QUERY_TOOL", "FINISH"]:
                raise ValueError(f"Invalid action: {thought['action']}")
            
            return thought
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON Parse Error: {e}")
            print(f"❌ Position: line {e.lineno}, column {e.colno}")
            print(f"❌ Failed text ({len(response_text)} chars):\n{response_text}\n")
            
            # Fallback: try to extract action manually
            if "FINISH" in response_text.upper():
                return {
                    "reasoning": "Parsing failed, but detected FINISH intent",
                    "action": "FINISH",
                    "final_answer": "Task completed with parsing issues"
                }
            
            # Default fallback
            return {
                "reasoning": f"JSON parse error: {str(e)}. Falling back to finish.",
                "action": "FINISH",
                "final_answer": f"Error: Could not parse response. Raw: {response_text[:200]}"
            }
        
        except Exception as e:
            print(f"❌ Unexpected Error in _think: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "reasoning": f"Error: {str(e)}",
                "action": "FINISH",
                "final_answer": f"Error: {str(e)}"
            }
    
    def _act(self, thought: Dict[str, Any]) -> Any:
        """Execute the action"""
        action = thought['action']
        
        try:
            if action == 'QUERY_TOOL':
                return self._query_tool(thought)
            elif action == 'USE_TOOL':
                return self._use_tool(thought)
            elif action == 'FINISH':
                return {"status": "finished"}
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _query_tool(self, thought: Dict[str, Any]) -> Dict[str, Any]:
        """Get tool schema"""
        tool_name = thought.get('tool')
        
        if not tool_name:
            return {"error": "Missing 'tool' parameter"}
        
        tool = self.tools.get(tool_name)
        
        if not tool:
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": list(self.tools.list_all().keys())
            }
        
        schema = tool.get_schema()
        print(f"   📋 Schema for {tool_name}")
        return schema
    
    def _use_tool(self, thought: Dict[str, Any]) -> Any:
        """Execute a tool"""
        tool_name = thought.get('tool')
        tool_action = thought.get('tool_action')
        parameters = thought.get('parameters', {})
        
        if not tool_name or not tool_action:
            return {"error": "Missing tool or tool_action"}
        
        tool = self.tools.get(tool_name)
        
        if not tool:
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": list(self.tools.list_all().keys())
            }
        
        print(f"   → Executing: {tool_name}.{tool_action}")
        
        result = tool.execute(tool_action, parameters, mode="real")
        
        if isinstance(result, dict) and "error" in result:
            result["fallback_suggestion"] = "Check tool parameters and try again"
        
        return result
    
    def _format_history(self) -> str:
        """Format conversation history"""
        if not self.conversation_history:
            return "Previous Steps: None yet"
        
        lines = ["Previous Steps:"]
        for entry in self.conversation_history[-5:]:  # Last 5 only
            lines.append(f"\nStep {entry['iteration']}:")
            lines.append(f"  Tool: {entry['thought'].get('tool', 'N/A')}")
            lines.append(f"  Action: {entry['thought'].get('tool_action', entry['thought']['action'])}")
            
            obs = entry['observation']
            if isinstance(obs, dict):
                # Highlight important results
                if 'number' in obs and 'html_url' in obs:
                    lines.append(f"  Result: ✅ GITHUB ISSUE CREATED - #{obs['number']} at {obs['html_url']}")
                elif 'error' in obs:
                    lines.append(f"  Result: ❌ Error - {str(obs['error'])[:100]}")
                else:
                    obs_str = str(obs)[:200]
                    lines.append(f"  Result: {obs_str}...")
            else:
                obs_str = str(obs)[:200]
                lines.append(f"  Result: {obs_str}...")
        
        return "\n".join(lines)
    
    def _extract_final_answer(self) -> str:
        """Extract answer from history"""
        for entry in reversed(self.conversation_history):
            obs = entry.get("observation", {})
            if isinstance(obs, dict):
                if 'number' in obs and 'html_url' in obs:
                    return f"Successfully created GitHub issue #{obs['number']} at {obs['html_url']}"
                elif obs.get("status") == 200:
                    return f"Task completed successfully. Data: {str(obs.get('data', ''))[:200]}"
        return "Task attempted"