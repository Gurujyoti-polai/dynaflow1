"""
ReAct Agent with Dynamic Tool System - FIXED
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
        consecutive_errors = 0  # Track consecutive errors
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            # Check progress before thinking
            progress = self._what_is_done()
            print(f"📊 Progress: weather={progress['weather_fetched']}, notion={progress['notion_created']}, github={progress['github_created']}")
            
            # Auto-finish if all required tasks complete
            goal_lower = user_goal.lower()

            if 'list' in goal_lower and 'github' in goal_lower:
                if progress.get('github_listed'):
                    print("🛑 GitHub repositories listed. Forcing FINISH.")
                    return {
                        "status": "success",
                        "result": observation.get("data"),
                        "iterations": iteration,
                        "trace": self.conversation_history + [{
                            "iteration": iteration,
                            "thought": thought,
                            "observation": observation
                        }]
                    }
            
            # Determine which tasks are needed
            needs_weather = 'weather' in goal_lower
            needs_notion = 'notion' in goal_lower
            needs_github = 'github' in goal_lower or 'issue' in goal_lower
            
            # Check if all needed tasks are done
            all_done = True
            if needs_weather and not progress['weather_fetched']:
                all_done = False
            if needs_notion and not progress['notion_created']:
                all_done = False
            if needs_github and not progress['github_created']:
                all_done = False
            
            if all_done and (needs_weather or needs_notion or needs_github):
                print("🎉 All required tasks completed! Auto-finishing.")
                
                # Build result message
                completed = []
                if progress['weather_fetched']:
                    completed.append("fetched weather data")
                if progress['notion_created']:
                    completed.append("created Notion page")
                if progress['github_created']:
                    completed.append("created GitHub issue")
                
                return {
                    "status": "success",
                    "result": f"Successfully {' and '.join(completed)}",
                    "iterations": iteration,
                    "trace": self.conversation_history
                }
            
            # THINK
            thought = self._think(user_goal)
            print(f"💭 Thought: {thought['reasoning'][:150]}...")
            
            # Check if done
            if thought['action'] == 'FINISH':
                print(f"✅ Done: {thought['final_answer']}")
                return {
                    "status": "success",
                    "result": thought['final_answer'],
                    "iterations": iteration,
                    "trace": self.conversation_history
                }
            
            # Check for repeated actions BEFORE executing
            action_key = f"{thought.get('action')}:{thought.get('tool')}:{thought.get('tool_action')}"
            repeated_actions[action_key] = repeated_actions.get(action_key, 0) + 1
            
            if repeated_actions[action_key] > 3:
                print(f"⚠️  Action repeated {repeated_actions[action_key]} times. Auto-finishing.")
                return {
                    "status": "failed",
                    "result": "Task failed: Agent stuck in loop trying the same action repeatedly",
                    "iterations": iteration,
                    "trace": self.conversation_history
                }
            
            # ACT
            print(f"🔧 Action: {thought['action']}")
            
            # Auto-replace placeholders before execution
            if thought['action'] == 'USE_TOOL':
                thought = self._replace_placeholders(thought)
            
            observation = self._act(thought)

            # Handle errors and track consecutive failures
            if isinstance(observation, dict):
                if "error" in observation or (observation.get("status", 200) >= 400):
                    consecutive_errors += 1
                    print(f"❌ Error (consecutive: {consecutive_errors})")
                    
                    if "error" in observation:
                        print(f"   {observation['error'][:100]}...")
                    if observation.get("status") == 401:
                        print(f"   🔑 Authentication failed - check API key")
                    
                    # If same error repeated 3 times, force finish
                    if consecutive_errors >= 3:
                        print(f"🛑 Too many consecutive errors - auto-finishing")
                        return {
                            "status": "failed",
                            "result": f"Task failed after {consecutive_errors} consecutive errors. Last error: {observation.get('error', 'Unknown')}",
                            "iterations": iteration,
                            "trace": self.conversation_history
                        }
                    
                    if "fallback_suggestion" in observation:
                        print(f"💡 Suggestion: {observation['fallback_suggestion']}")
                else:
                    consecutive_errors = 0  # Reset on success
                    
                    if "number" in observation and "html_url" in observation:
                        print(f"✅✅✅ SUCCESS! GitHub issue created: #{observation.get('number')}")
                        print(f"🔗 URL: {observation.get('html_url')}")
                    elif observation.get("status") == 200:
                        print(f"✅ HTTP 200 - Success")
                    else:
                        print(f"👁️  Observation: {str(observation)[:200]}...")
            else:
                consecutive_errors = 0
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
        Agent reasons about what to do next
        """
        history_text = self._format_history()
        tool_manifest = self.tools.list_manifest()
        progress = self._what_is_done()
        
        # Count failures for each tool
        tool_failures = {}
        for entry in self.conversation_history:
            tool_name = entry.get('thought', {}).get('tool')
            obs = entry.get('observation', {})
            
            if tool_name and isinstance(obs, dict):
                if 'error' in obs or obs.get('status', 200) >= 400:
                    tool_failures[tool_name] = tool_failures.get(tool_name, 0) + 1
        
        print(f"📊 Progress: weather={progress['weather_fetched']}, notion={progress['notion_created']}")
        print(f"📊 Failures: {tool_failures}")
        
        # Auto-finish conditions
        if tool_failures.get('http', 0) >= 2 and not progress['weather_fetched']:
            print("🛑 Too many HTTP failures - auto-finishing")
            return {
                "reasoning": "Weather API failed multiple times due to authentication",
                "action": "FINISH",
                "final_answer": f"Failed to fetch weather data after {tool_failures['http']} attempts. Please check your OpenWeatherMap API key configuration."
            }
        
        if tool_failures.get('notion', 0) >= 2 and progress['weather_fetched']:
            print("🛑 Too many Notion failures but weather succeeded - auto-finishing")
            return {
                "reasoning": "Weather fetched successfully but Notion failed multiple times",
                "action": "FINISH",
                "final_answer": "Successfully fetched weather data. Notion integration failed - please check NOTION_TOKEN and NOTION_DB_ID configuration."
            }
        
        # Get API key and config status for the prompt
        weather_api_key = os.environ.get('OPENWEATHER_API_KEY', 'NOT_SET')
        notion_token = os.environ.get('NOTION_TOKEN', 'NOT_SET')
        notion_db_id = os.environ.get('NOTION_DB_ID', 'NOT_SET')
        github_token = os.environ.get('GITHUB_TOKEN', 'NOT_SET')
        
        prompt = f"""You are an AI agent that executes workflows. You must respond with ONLY valid JSON.

USER GOAL: {user_goal}

{history_text}

Available Tools:
{tool_manifest}

ENVIRONMENT CONFIGURATION STATUS:
- OpenWeatherMap API Key: {'✓ Set' if weather_api_key != 'NOT_SET' else '✗ NOT SET (use wttr.in instead)'}
- Notion Token: {'✓ Set (' + notion_token[:8] + '...)' if notion_token != 'NOT_SET' else '✗ NOT SET'}
- Notion Database ID: {'✓ Set (' + notion_db_id[:8] + '...)' if notion_db_id != 'NOT_SET' else '✗ NOT SET'}
- GitHub Token: {'✓ Set (' + github_token[:8] + '...)' if github_token != 'NOT_SET' else '✗ NOT SET'}

CRITICAL: If any required config is NOT SET, do not attempt to use that tool - use FINISH instead with an explanation.

⚠️ CRITICAL RULES:
1. CHECK PREVIOUS STEPS - Never repeat failed actions
2. If HTTP 401 error, the API key is wrong - try a different approach or FINISH
3. If same tool fails 2+ times, either try different parameters OR use FINISH
4. NEVER use placeholder values like "YOUR_API_KEY" or "YOUR_DATABASE_ID"
5. NEVER use template variables like {{weather_temperature}} or {{weather_condition}}
6. When using data from previous steps, extract the ACTUAL VALUES from the observation
7. If config shows "NOT SET", skip that tool and use FINISH with error message
8. The tools will automatically read environment variables - DO NOT pass them explicitly

USING DATA FROM PREVIOUS STEPS:
- If you fetched weather in step 1, look at that step's observation for actual temperature value
- Extract the real number (e.g., 31) and real text (e.g., "Sunny") from the data
- Use actual values, NOT placeholders like {{temperature}} or {{condition}}
- Example: If observation shows {{"temp_c": 31}}, use "31" not "{{temp_c}}"

📋 ALLOWED ACTIONS:

1. USE_TOOL - Execute a tool action
   {{"action": "USE_TOOL", "reasoning": "...", "tool": "tool_name", "tool_action": "action", "parameters": {{...}}}}
   
   Examples:
   - Weather: {{"action": "USE_TOOL", "tool": "http", "tool_action": "GET", "parameters": {{"url": "https://wttr.in/Mumbai?format=j1"}}}}
   - Notion: {{"action": "USE_TOOL", "tool": "notion", "tool_action": "create_page", "parameters": {{"title": "Weather Report", "properties": {{"Temperature": "31°C", "City": "Mumbai"}}}}}}
   - GitHub: {{"action": "USE_TOOL", "tool": "github", "tool_action": "create_issue", "parameters": {{"repo": "username/repo-name", "title": "Issue Title", "body": "Description"}}}}

2. QUERY_TOOL - Get tool schema
   {{"action": "QUERY_TOOL", "reasoning": "...", "tool": "tool_name"}}

3. FINISH - Task complete or failed
   {{"action": "FINISH", "reasoning": "...", "final_answer": "Summary of what was accomplished or why it failed"}}

🎯 WORKFLOW LOGIC:

If goal = "Get weather and add to Notion":
  Step 1: Fetch weather using wttr.in (no API key needed)
    - USE_TOOL with http.GET: https://wttr.in/Mumbai?format=j1
  
  Step 2: Add to Notion with SIMPLE parameters (tool handles the complex format)
    - USE_TOOL with notion.create_page
    - Parameters: {{"title": "Weather Report", "properties": {{"Temperature": "31°C", "Condition": "Sunny"}}}}
    - DO NOT include database_id - it's auto-injected from NOTION_DB_ID
    - DO NOT use complex Notion API format - use simple key-value pairs
  
  Step 3: If either fails 2+ times, use FINISH with explanation

PROGRESS:
- Weather fetched: {"YES ✓" if progress['weather_fetched'] else "NO"}
- Notion created: {"YES ✓" if progress['notion_created'] else "NO"}

FAILURES:
{json.dumps(tool_failures, indent=2)}

NEXT STEP:
{
    "FINISH - Too many HTTP failures" if tool_failures.get('http', 0) >= 2 and not progress['weather_fetched']
    else "FINISH - Weather done, Notion failed" if progress['weather_fetched'] and tool_failures.get('notion', 0) >= 2
    else "Try wttr.in for weather" if tool_failures.get('http', 0) >= 1 and not progress['weather_fetched']
    else "Fetch weather" if not progress['weather_fetched']
    else "Add to Notion" if progress['weather_fetched'] and not progress['notion_created']
    else "FINISH - All done!"
}

RESPOND WITH JSON ONLY:"""
        
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
            result["fallback_suggestion"] = "Check tool parameters and try again, or try a different approach"
        
        return result
    
    def _format_history(self) -> str:
        """Format conversation history with emphasis on available data"""
        if not self.conversation_history:
            return "Previous Steps: None yet"
        
        lines = ["Previous Steps:"]
        for entry in self.conversation_history[-5:]:  # Last 5 only
            lines.append(f"\nStep {entry['iteration']}:")
            lines.append(f"  Tool: {entry['thought'].get('tool', 'N/A')}")
            lines.append(f"  Action: {entry['thought'].get('tool_action', entry['thought']['action'])}")
            
            obs = entry['observation']
            if isinstance(obs, dict):
                # Highlight important results with data extraction hints
                if 'number' in obs and 'html_url' in obs:
                    lines.append(f"  Result: ✅ SUCCESS - GitHub issue #{obs['number']}")
                elif obs.get('status') == 401:
                    lines.append(f"  Result: ❌ HTTP 401 - Authentication failed")
                elif 'error' in obs:
                    lines.append(f"  Result: ❌ Error - {str(obs['error'])[:100]}")
                elif obs.get('status') == 200:
                    lines.append(f"  Result: ✅ HTTP 200 - Success")
                    
                    # Show data extraction hints for weather
                    tool = entry['thought'].get('tool')
                    if tool == 'http':
                        data = obs.get('data', {})
                        # Try to extract weather info
                        if 'current_condition' in str(data):
                            lines.append(f"  💡 Weather data available - extract actual values from observation")
                            # Show a preview of available data
                            try:
                                current = data.get('current_condition', [{}])[0]
                                temp = current.get('temp_C', 'N/A')
                                lines.append(f"     Example: temp_C = {temp}")
                            except:
                                pass
                else:
                    obs_str = str(obs)[:200]
                    lines.append(f"  Result: {obs_str}...")
            else:
                obs_str = str(obs)[:200]
                lines.append(f"  Result: {obs_str}...")
        
        return "\n".join(lines)
    
    def _replace_placeholders(self, thought: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automatically replace placeholder variables with actual values from history
        Handles patterns like: {variable}, {{variable}}, {weather_temp}, etc.
        """
        import re
        
        # Get available data
        available_data = self._extract_available_data()
        
        # Only process if we have weather data
        if not available_data.get('weather'):
            return thought
        
        weather = available_data['weather']
        
        # Get parameters
        params = thought.get('parameters', {})
        if not params:
            return thought
        
        # Replacement map - maps placeholder patterns to actual values
        replacements = {
            # Temperature patterns
            r'\{\{?temp_?c\}?\}?': weather.get('temperature', ''),
            r'\{\{?temperature\}?\}?': weather.get('temperature', ''),
            r'\{\{?weather_temperature\}?\}?': weather.get('temperature', ''),
            
            # Condition patterns
            r'\{\{?condition\}?\}?': weather.get('condition', ''),
            r'\{\{?weather_condition\}?\}?': weather.get('condition', ''),
            r'\{\{?weather_?desc\}?\}?': weather.get('condition', ''),
            
            # Humidity patterns
            r'\{\{?humidity\}?\}?': weather.get('humidity', ''),
        }
        
        # Function to recursively replace in dict
        def replace_in_dict(obj):
            if isinstance(obj, dict):
                return {k: replace_in_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_in_dict(item) for item in obj]
            elif isinstance(obj, str):
                # Try each replacement pattern
                result = obj
                for pattern, value in replacements.items():
                    if re.search(pattern, result, re.IGNORECASE):
                        result = re.sub(pattern, str(value), result, flags=re.IGNORECASE)
                        print(f"   🔄 Replaced placeholder '{obj}' → '{result}'")
                return result
            else:
                return obj
        
        # Replace placeholders in parameters
        thought['parameters'] = replace_in_dict(params)
        
        return thought
    
    def _extract_final_answer(self) -> str:
        """Extract answer from history"""
        for entry in reversed(self.conversation_history):
            obs = entry.get("observation", {})
            if isinstance(obs, dict):
                if 'number' in obs and 'html_url' in obs:
                    return f"Successfully created GitHub issue #{obs['number']} at {obs['html_url']}"
                elif obs.get("status") == 200:
                    return f"Task completed successfully. Data: {str(obs.get('data', ''))[:200]}"
        return "Task attempted but no successful completion detected"
    
    def _what_is_done(self) -> Dict[str, bool]:
        """Check what has been accomplished"""
        done = {
            "weather_fetched": False,
            "notion_created": False,
            "github_created": False,
            "github_listed": False,
            "weather_data": None
        }
        
        for entry in self.conversation_history:
            obs = entry.get('observation', {})
            thought = entry.get('thought', {})
            tool = thought.get('tool', '')
            
            if isinstance(obs, dict):
                # Check weather - either OpenWeather or wttr.in
                if obs.get('status') == 200 and tool == 'http':
                    data = obs.get('data', {})
                    # OpenWeather format or wttr.in
                    if 'current_condition' in str(data) or 'main' in data or 'weather' in data:
                        done['weather_fetched'] = True
                        done['weather_data'] = data
                
                # Check Notion - look for successful page creation
                if obs.get('status') == 200 and tool == 'notion':
                    # Check for page_id or url in response
                    if obs.get('page_id') or obs.get('url') or 'message' in obs:
                        done['notion_created'] = True
                        print(f"   ✅ Notion page created: {obs.get('url', 'Success')}")
                
                # Check GitHub - look for successful issue/PR creation
                if tool == 'github':
                    if obs.get('status') == 200 and isinstance(obs.get('data'), list):
                        done['github_listed'] = True
                    # Check for issue number and URL (from our smart tool)
                    if obs.get('number') and obs.get('html_url'):
                        done['github_created'] = True
                        print(f"   ✅ GitHub issue #{obs.get('number')} created: {obs.get('html_url')}")
                    # Also check raw data structure (from original tool)
                    elif 'number' in obs and 'html_url' in obs:
                        done['github_created'] = True
                        print(f"   ✅ GitHub issue #{obs.get('number')} created")
        
        return done
    
    def _extract_available_data(self) -> Dict[str, Any]:
        """Extract data from previous steps that can be used"""
        data = {
            "weather": None,
            "notion_url": None,
            "github_url": None
        }
        
        for entry in self.conversation_history:
            obs = entry.get('observation', {})
            thought = entry.get('thought', {})
            
            if isinstance(obs, dict) and obs.get('status') == 200:
                tool = thought.get('tool', '')
                
                # Extract weather data
                if tool == 'http':
                    raw_data = obs.get('data', {})
                    if 'current_condition' in str(raw_data):
                        try:
                            current = raw_data.get('current_condition', [{}])[0]
                            data['weather'] = {
                                'temperature': current.get('temp_C', ''),
                                'condition': current.get('weatherDesc', [{}])[0].get('value', ''),
                                'humidity': current.get('humidity', ''),
                                'feels_like': current.get('FeelsLikeC', '')
                            }
                        except:
                            pass
                
                # Extract Notion URL
                elif tool == 'notion':
                    data['notion_url'] = obs.get('url', '')
                
                # Extract GitHub URL
                elif tool == 'github':
                    data['github_url'] = obs.get('html_url', '')
        
        return data