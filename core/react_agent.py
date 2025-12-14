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

            #  Check if we have weather data and should move to next step
            if iteration > 1:
                last_obs = self.conversation_history[-1].get('observation', {})
                if isinstance(last_obs, dict) and last_obs.get('status') == 200:
                    data = last_obs.get('data', {})
                    if 'current_condition' in data and 'notion' in user_goal.lower():
                        print("✅ Weather data obtained. Moving to Notion...")
                        # Continue to let agent think about Notion
            
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
                elif observation.get("status") == 401:
                    print(f"🔒 Authentication failed - stopping retry loop")
                    print(f"💡 Hint: Check NOTION_TOKEN and NOTION_DB_ID environment variables")
                    return {
                        "status": "auth_error",
                        "result": "Authentication failed. Weather data retrieved successfully but could not add to Notion due to invalid credentials.",
                        "iterations": iteration,
                        "trace": self.conversation_history
                    }
                elif observation.get("status") == 200:
                    data = observation.get("data", {})
                    # Check if this is a successful Notion page creation
                    if isinstance(data, dict) and data.get("object") == "page":
                        print(f"✅✅✅ SUCCESS! Notion page created: {data.get('id')}")
                        print(f"🎉 Task completed successfully!")
                        # Force FINISH on next iteration by adding to history
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
        
        # DON'T remove // comments - they might be part of URLs!
        # Only remove comments that are clearly standalone (not in strings)
        # For now, skip comment removal to avoid breaking URLs
        
        result = text.strip()
        print(f"   Final cleaned ({len(result)} chars)")
        return result
    
    def _extract_city_from_goal(self, goal: str) -> str:
        """
        Extract city name from user goal
        Simple extraction - looks for common patterns
        """
        goal_lower = goal.lower()
        
        # Common patterns: "get X weather", "weather in X", "X weather"
        patterns = [
            r'(?:get|fetch|retrieve)\s+(\w+)\s+weather',
            r'weather\s+(?:in|for|of)\s+(\w+)',
            r'(\w+)\s+weather',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, goal_lower)
            if match:
                city = match.group(1).capitalize()
                print(f"🌍 Extracted city: {city}")
                return city
        
        # Default fallback
        print(f"⚠️  Could not extract city, using Mumbai as default")
        return "Mumbai"
    
    def _think(self, user_goal: str) -> Dict[str, Any]:
        """
        Agent reasons about what to do next
        """
        history_text = self._format_history()
        tool_manifest = self.tools.list_manifest()
        
        # Extract city name from goal (simple extraction)
        city = self._extract_city_from_goal(user_goal)
        
        # Check if we have weather data
        has_weather = False
        weather_data = None
        weather_temp = None
        has_auth_error = False
        notion_success = False
        
        for entry in self.conversation_history:
            obs = entry.get('observation', {})
            thought = entry.get('thought', {})
            
            if isinstance(obs, dict):
                # Check for weather data
                if obs.get('status') == 200:
                    data = obs.get('data', {})
                    if isinstance(data, dict) and 'current_condition' in data:
                        has_weather = True
                        weather_data = data
                        try:
                            weather_temp = int(data['current_condition'][0]['temp_C'])
                        except (KeyError, IndexError, ValueError):
                            weather_temp = 25
                    # Check if this was a successful Notion POST
                    elif 'object' in data and data.get('object') == 'page':
                        notion_success = True
                # Check for authentication errors
                if obs.get('status') == 401:
                    has_auth_error = True
        
        # Get environment variables
        notion_token = os.environ.get('NOTION_TOKEN', '')
        notion_db_id = os.environ.get('NOTION_DB_ID', '')
        
        prompt = f"""You are an AI agent that executes workflows. You must respond with ONLY valid JSON.

USER GOAL: {user_goal}
TARGET CITY: {city}

{history_text}

Available Tools:
{tool_manifest}

CURRENT STATUS:
- Have weather data: {"YES ✓" if has_weather else "NO"}
- Weather temperature: {weather_temp if weather_temp else "N/A"}°C
- Notion credentials: {"CONFIGURED ✓" if notion_token and notion_db_id else "MISSING ⚠️"}
- Notion POST success: {"YES ✓✓✓ ALREADY DONE - DO NOT REPEAT!" if notion_success else "NOT YET"}
- Previous auth error: {"YES - STOP" if has_auth_error else "NO"}

🚨 CRITICAL RULES - READ CAREFULLY:
1. Look at "Previous Steps" above - if you see "✅ NOTION PAGE CREATED SUCCESSFULLY" → TASK IS DONE → Use FINISH action immediately
2. NEVER POST to Notion twice - if it succeeded once, you're DONE
3. If Notion POST failed with 401 → FINISH with error
4. Only POST to Notion if you haven't already succeeded

DECISION TREE:
- Notion already succeeded? → FINISH (YOU'RE DONE!)
- Have weather + got 401? → FINISH with error
- Have weather + haven't tried Notion yet? → POST to Notion
- Don't have weather? → GET weather for {city}
- Otherwise? → FINISH

YOUR NEXT ACTION:
{"🎯 FINISH - You already created the Notion page successfully!" if notion_success else "🔒 FINISH - Auth failed" if has_auth_error else f"📤 POST to Notion (first attempt)" if has_weather and notion_token else f"🌤️ GET weather for {city}" if not has_weather else "⚠️ FINISH - No credentials"}

RESPOND WITH ONLY ONE OF THESE JSON FORMATS:

Option 1 - FINISH (if task is done or Notion already succeeded):
{{
  "reasoning": "task completed - Notion page was already created in previous step",
  "action": "FINISH",
  "final_answer": "Successfully retrieved {city} weather ({weather_temp}°C) and added to Notion database."
}}

Option 2 - GET weather (if don't have it yet):
{{
  "reasoning": "fetching {city} weather data",
  "action": "USE_TOOL",
  "tool": "http",
  "tool_action": "GET",
  "parameters": {{
    "url": "https://wttr.in/{city}?format=j1"
  }}
}}

Option 3 - POST to Notion (ONLY if have weather AND haven't succeeded yet):
{{
  "reasoning": "adding {city} weather to Notion database for the first time",
  "action": "USE_TOOL",
  "tool": "http",
  "tool_action": "POST",
  "parameters": {{
    "url": "https://api.notion.com/v1/pages",
    "headers": {{
      "Authorization": "Bearer {notion_token}",
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json"
    }},
    "body": {{
      "parent": {{"database_id": "{notion_db_id}"}},
      "properties": {{
        "Name": {{"title": [{{"text": {{"content": "{city} Weather - {weather_temp}°C"}}}}]}},
        "Temperature": {{"number": {weather_temp or 25}}}
      }}
    }}
  }}
}}

⚠️ WARNING: If you see "NOTION PAGE CREATED SUCCESSFULLY" in Previous Steps, you MUST use FINISH. Creating duplicate pages is wrong!"""
        
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
                "available_primitives": ["http", "data", "file"]
            }
        
        print(f"   → Executing: {tool_name}.{tool_action}")
        
        result = tool.execute(tool_action, parameters, mode="real")
        
        if isinstance(result, dict) and "error" in result:
            result["fallback_suggestion"] = "Try using http primitives directly"
        
        return result
    
    def _format_history(self) -> str:
        """Format conversation history"""
        if not self.conversation_history:
            return "Previous Steps: None yet"
        
        lines = ["Previous Steps:"]
        for entry in self.conversation_history[-5:]:  # Last 5 only
            lines.append(f"\nStep {entry['iteration']}:")
            lines.append(f"  Action: {entry['thought']['action']}")
            
            obs = entry['observation']
            if isinstance(obs, dict):
                obs_str = str(obs)[:300]
            else:
                obs_str = str(obs)[:300]
            
            lines.append(f"  Result: {obs_str}...")
        
        return "\n".join(lines)
    
    def _extract_final_answer(self) -> str:
        """Extract answer from history"""
        for entry in reversed(self.conversation_history):
            obs = entry.get("observation", {})
            if isinstance(obs, dict) and obs.get("status") == 200:
                return f"Task completed. Data: {str(obs.get('data', ''))[:200]}"
        return "Task attempted"