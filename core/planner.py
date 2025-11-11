import os
import json
from core.schemas import WorkflowPlan
from dotenv import load_dotenv

load_dotenv()

USE_REAL_LLM = bool(os.getenv("GOOGLE_API_KEY"))

if USE_REAL_LLM:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

def parse_prompt_to_plan(prompt: str) -> WorkflowPlan:
    """
    Parse ANY natural language prompt into executable workflow steps.
    No hardcoded apps - fully dynamic.
    """
    if not USE_REAL_LLM:
        # Mock: Create a simple workflow from the prompt
        return WorkflowPlan(
            name="Mock Workflow",
            description=prompt,
            steps=[
                {
                    "step_id": "step_1",
                    "step_type": "custom",
                    "description": f"Execute: {prompt}",
                    "config": {"action": "mock_execution", "input": prompt}
                }
            ]
        )

    system_prompt = """
You are a workflow orchestration AI. Convert ANY user request into executable workflow steps.

Available step types:
1. http_request: Make HTTP API calls (GET, POST, PUT, DELETE, etc.)
2. transform: Transform/process data (extract_json_path, template, map, filter, aggregate)
3. condition: If/else logic
4. loop: Iterate over data
5. wait: Delay execution
6. plugin: Use a registered plugin
7. custom: Any other operation

IMPORTANT: Environment Variable Handling
- Use {{ENV_VAR_NAME}} or YOUR_ENV_VAR_NAME for credentials
- Common patterns:
  * {{OPENWEATHER_API_KEY}} or YOUR_OPENWEATHER_API_KEY
  * {{NOTION_TOKEN}} or YOUR_NOTION_TOKEN
  * {{SLACK_TOKEN}} or YOUR_SLACK_TOKEN
  * {{NOTION_DATABASE_ID}} or YOUR_NOTION_DATABASE_ID

CRITICAL: Notion API Structure
When creating Notion pages/entries, the parent structure matters:

For DATABASE (most common):
{
  "method": "POST",
  "url": "https://api.notion.com/v1/pages",
  "headers": {
    "Authorization": "Bearer {{NOTION_TOKEN}}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
  },
  "body": {
    "parent": {
      "database_id": "{{NOTION_DATABASE_ID}}"
    },
    "properties": {
      "Name": {
        "title": [
          {
            "text": {
              "content": "Your title here"
            }
          }
        ]
      }
    }
  }
}

For PAGE parent:
{
  "parent": {
    "page_id": "{{NOTION_PAGE_ID}}"
  }
}

Transform Operations:
- extract_json_path or get_field: Extract nested field
  Config: {"operation": "extract_json_path", "path": "main.temp", "source": "step_1"}
- template: String substitution
  Config: {"operation": "template", "template": "Temperature is {{step_1.result.main.temp}}°C"}

Return JSON in this format:
{
  "name": "Workflow Name",
  "description": "What this workflow does",
  "steps": [
    {
      "step_id": "step_1",
      "step_type": "http_request",
      "description": "Fetch weather data",
      "config": {
        "method": "GET",
        "url": "https://api.openweathermap.org/data/2.5/weather",
        "params": {
          "q": "Mumbai",
          "units": "metric",
          "appid": "{{OPENWEATHER_API_KEY}}"
        }
      }
    },
    {
      "step_id": "step_2",
      "step_type": "transform",
      "description": "Extract temperature",
      "config": {
        "operation": "extract_json_path",
        "path": "main.temp",
        "source": "step_1"
      },
      "depends_on": ["step_1"]
    },
    {
      "step_id": "step_3",
      "step_type": "http_request",
      "description": "Save to Notion database",
      "config": {
        "method": "POST",
        "url": "https://api.notion.com/v1/pages",
        "headers": {
          "Authorization": "Bearer {{NOTION_TOKEN}}",
          "Notion-Version": "2022-06-28",
          "Content-Type": "application/json"
        },
        "body": {
          "parent": {
            "database_id": "{{NOTION_DATABASE_ID}}"
          },
          "properties": {
            "Name": {
              "title": [{"text": {"content": "Mumbai Weather - {{CURRENT_DATE_TIME}}"}}]
            },
            "Temperature": {
              "number": "{{step_2.result}}"
            }
          }
        }
      },
      "depends_on": ["step_2"]
    }
  ]
}

Examples:
- "Fetch weather from OpenWeather API and send to Slack"
- "Read GitHub stars, calculate growth rate, post to Twitter"
- "Get Mumbai temperature and save to Notion database"
- "Every hour, check stock price API, if > $150 send Telegram message"

Be creative! Figure out the APIs, transformations, and logic needed.
IMPORTANT: Return ONLY valid JSON, no markdown.
"""

    full_prompt = f"{system_prompt}\n\nUser request: {prompt}"
    response = llm.invoke(full_prompt)
    content = response.content.strip()

    # Clean markdown
    if content.startswith("```json"):
        content = content.split("```json")[1].split("```")[0].strip()
    elif content.startswith("```"):
        content = content.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(content)
        return WorkflowPlan(**parsed)
    except Exception as e:
        raise ValueError(f"Failed to parse LLM JSON: {e}\nContent:\n{content}")