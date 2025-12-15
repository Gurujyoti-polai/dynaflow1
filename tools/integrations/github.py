# tools/integrations/github.py

from typing import Dict, Any, Optional
import httpx
import os
from tools.base import ToolBase


class GithubTool(ToolBase):
    """
    Smart GitHub integration tool with:
    - Automatic token injection
    - Simplified parameters for LLM
    - Better error messages
    - Status code handling
    """

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        return "GitHub operations: create issues, PRs, list repos, etc."
    
    @property
    def category(self) -> str:
        return "integration"

    # =========================
    # 🔹 SCHEMA FOR LLM
    # =========================
    def get_schema(self) -> Dict[str, Any]:
        """Return simplified schema for LLM"""
        github_token = os.getenv("GITHUB_TOKEN", "NOT_SET")
        
        return {
            "tool": self.name,
            "description": self.description,
            "environment": {
                "GITHUB_TOKEN": "✓ Set" if github_token != "NOT_SET" else "✗ NOT SET"
            },
            "actions": {
                "create_issue": {
                    "description": "Create a GitHub issue in a repository",
                    "required_env": ["GITHUB_TOKEN"],
                    "parameters": {
                        "repo": {
                            "type": "string",
                            "required": True,
                            "description": "Repository in format 'owner/repo' (e.g., 'octocat/Hello-World')",
                            "example": "username/repository-name"
                        },
                        "title": {
                            "type": "string",
                            "required": True,
                            "description": "Issue title"
                        },
                        "body": {
                            "type": "string",
                            "required": False,
                            "description": "Issue description/body (markdown supported)"
                        },
                        "labels": {
                            "type": "array",
                            "required": False,
                            "description": "List of label names (e.g., ['bug', 'enhancement'])"
                        },
                        "assignees": {
                            "type": "array",
                            "required": False,
                            "description": "List of GitHub usernames to assign"
                        }
                    },
                    "example": {
                        "repo": "username/my-project",
                        "title": "Weather API Integration",
                        "body": "Need to integrate weather API for Mumbai",
                        "labels": ["enhancement"]
                    }
                },
                "create_pull_request": {
                    "description": "Create a pull request",
                    "required_env": ["GITHUB_TOKEN"],
                    "parameters": {
                        "repo": {
                            "type": "string",
                            "required": True,
                            "description": "Repository in format 'owner/repo'"
                        },
                        "title": {
                            "type": "string",
                            "required": True,
                            "description": "PR title"
                        },
                        "head": {
                            "type": "string",
                            "required": True,
                            "description": "Branch containing changes (e.g., 'feature-branch')"
                        },
                        "base": {
                            "type": "string",
                            "required": True,
                            "description": "Branch to merge into (usually 'main' or 'master')"
                        },
                        "body": {
                            "type": "string",
                            "required": False,
                            "description": "PR description"
                        }
                    },
                    "example": {
                        "repo": "username/my-project",
                        "title": "Add weather feature",
                        "head": "feature/weather",
                        "base": "main",
                        "body": "This PR adds weather integration"
                    }
                },
                "list_repos": {
                    "description": "List repositories for a user or organization",
                    "required_env": ["GITHUB_TOKEN"],
                    "parameters": {
                        "user": {
                            "type": "string",
                            "required": False,
                            "description": "GitHub username (uses authenticated user if not provided)"
                        },
                        "type": {
                            "type": "string",
                            "required": False,
                            "description": "Filter: 'all', 'owner', 'member' (default: 'owner')"
                        },
                        "sort": {
                            "type": "string",
                            "required": False,
                            "description": "Sort by: 'created', 'updated', 'pushed', 'full_name'"
                        }
                    }
                },
                "get_issue": {
                    "description": "Get details of a specific issue",
                    "required_env": ["GITHUB_TOKEN"],
                    "parameters": {
                        "repo": {
                            "type": "string",
                            "required": True,
                            "description": "Repository in format 'owner/repo'"
                        },
                        "issue_number": {
                            "type": "integer",
                            "required": True,
                            "description": "Issue number"
                        }
                    }
                }
            }
        }

    # =========================
    # 🔹 MAIN EXECUTION
    # =========================
    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        """Execute GitHub action with smart error handling"""
        
        if mode == "mock":
            return {
                "status": 200,
                "message": f"Mock execution: {action}",
                "data": {"mock": True}
            }

        # Check token
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return {
                "error": "GITHUB_TOKEN environment variable not set",
                "status": 401,
                "suggestion": "Set GITHUB_TOKEN in your .env file with a GitHub personal access token"
            }

        # Route to specific action
        try:
            if action == "create_issue":
                return self._create_issue(config, token)
            elif action == "create_pull_request":
                return self._create_pull_request(config, token)
            elif action == "list_repos":
                return self._list_repos(config, token)
            elif action == "get_issue":
                return self._get_issue(config, token)
            else:
                return {
                    "error": f"Unknown GitHub action '{action}'",
                    "status": 400,
                    "available_actions": ["create_issue", "create_pull_request", "list_repos", "get_issue"]
                }

        except httpx.HTTPStatusError as e:
            return self._handle_http_error(e)
        except Exception as e:
            return {
                "error": str(e),
                "status": 500
            }

    # =========================
    # 🔹 ACTION IMPLEMENTATIONS
    # =========================
    
    def _create_issue(self, config: Dict[str, Any], token: str) -> Dict[str, Any]:
        """Create a GitHub issue with validation"""
        
        repo = config.get("repo")
        title = config.get("title")
        body = config.get("body", "")
        labels = config.get("labels", [])
        assignees = config.get("assignees", [])

        # Validate required fields
        if not repo:
            return {
                "error": "Missing required parameter: 'repo'",
                "status": 400,
                "suggestion": "Provide repo in format 'owner/repo' (e.g., 'octocat/Hello-World')"
            }
        
        if not title:
            return {
                "error": "Missing required parameter: 'title'",
                "status": 400
            }

        # Validate repo format
        if "/" not in repo:
            return {
                "error": f"Invalid repo format: '{repo}'",
                "status": 400,
                "suggestion": "Use format 'owner/repo' (e.g., 'username/repository-name')"
            }

        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        payload = {
            "title": title,
            "body": body
        }
        
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees

        print(f"   📤 Creating issue in {repo}")
        print(f"   📝 Title: {title[:50]}...")

        with httpx.Client(timeout=30) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                "status": 200,
                "data": result,
                "number": result.get("number"),
                "html_url": result.get("html_url"),
                "state": result.get("state"),
                "message": f"✅ Issue #{result.get('number')} created successfully"
            }

    def _create_pull_request(self, config: Dict[str, Any], token: str) -> Dict[str, Any]:
        """Create a pull request"""
        
        repo = config.get("repo")
        title = config.get("title")
        head = config.get("head")
        base = config.get("base", "main")
        body = config.get("body", "")

        # Validate
        if not all([repo, title, head]):
            missing = [k for k in ["repo", "title", "head"] if not config.get(k)]
            return {
                "error": f"Missing required parameters: {', '.join(missing)}",
                "status": 400
            }

        url = f"https://api.github.com/repos/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body
        }

        print(f"   📤 Creating PR: {head} → {base}")

        with httpx.Client(timeout=30) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                "status": 200,
                "data": result,
                "number": result.get("number"),
                "html_url": result.get("html_url"),
                "state": result.get("state"),
                "message": f"✅ PR #{result.get('number')} created successfully"
            }

    def _list_repos(self, config: Dict[str, Any], token: str) -> Dict[str, Any]:
        """List repositories"""
        
        user = config.get("user")
        repo_type = config.get("type", "owner")
        sort = config.get("sort", "updated")

        # If no user specified, use authenticated user's repos
        if user:
            url = f"https://api.github.com/users/{user}/repos"
        else:
            url = "https://api.github.com/user/repos"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        params = {
            "type": repo_type,
            "sort": sort,
            "per_page": 30
        }

        with httpx.Client(timeout=30) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            repos = response.json()
            
            # Simplify response
            simplified = [
                {
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "description": r.get("description"),
                    "url": r.get("html_url"),
                    "private": r.get("private"),
                    "language": r.get("language")
                }
                for r in repos
            ]
            
            return {
                "status": 200,
                "data": simplified,
                "count": len(simplified),
                "message": f"Found {len(simplified)} repositories"
            }

    def _get_issue(self, config: Dict[str, Any], token: str) -> Dict[str, Any]:
        """Get a specific issue"""
        
        repo = config.get("repo")
        issue_number = config.get("issue_number")

        if not repo or not issue_number:
            return {
                "error": "Missing required parameters: 'repo' and 'issue_number'",
                "status": 400
            }

        url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        with httpx.Client(timeout=30) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                "status": 200,
                "data": result,
                "number": result.get("number"),
                "title": result.get("title"),
                "state": result.get("state"),
                "html_url": result.get("html_url")
            }

    # =========================
    # 🔹 ERROR HANDLING
    # =========================
    
    def _handle_http_error(self, error: httpx.HTTPStatusError) -> Dict[str, Any]:
        """Handle HTTP errors with helpful messages"""
        
        status_code = error.response.status_code
        
        # Parse GitHub error message
        try:
            error_data = error.response.json()
            message = error_data.get("message", str(error))
        except:
            message = str(error)

        # Provide specific guidance based on status code
        if status_code == 401:
            suggestion = "Check that GITHUB_TOKEN is valid and not expired"
        elif status_code == 403:
            suggestion = "Token lacks required permissions or rate limit exceeded"
        elif status_code == 404:
            suggestion = "Repository not found or you don't have access"
        elif status_code == 422:
            suggestion = "Invalid parameters - check repo format and required fields"
        else:
            suggestion = "Check the GitHub API documentation"

        return {
            "error": f"GitHub API error: {message}",
            "status": status_code,
            "suggestion": suggestion
        }