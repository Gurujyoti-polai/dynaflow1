from typing import Dict, Any
import httpx
import os
from ..base import ToolBase


class GithubTool(ToolBase):
    """GitHub integration tool supporting multiple actions."""

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        return "Performs GitHub operations like creating issues, PRs, repos, etc."
    
    @property
    def category(self) -> str:
        return "integration"

    # -------------------------------
    # MAIN EXECUTION ENTRYPOINT
    # -------------------------------
    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        """
        Executes a GitHub action.
        Pattern:
            execute("create_issue", {...})
            execute("create_pr", {...})
        """

        if mode == "mock":
            return {"status": "mock", "action": action, "config": config}

        # Dispatch to specific function
        if action == "create_issue":
            return self._create_issue(config)

        elif action == "create_pull_request":
            return self._create_pull_request(config)

        elif action == "list_repos":
            return self._list_repos(config)

        # -----------------------------------------
        # ❗ If action does not exist — agent fallback
        # -----------------------------------------
        return {
            "error": f"Unknown GitHub action '{action}'. "
                     f"Available: create_issue, create_pull_request, list_repos"
        }

    # -------------------------------
    # ACTION IMPLEMENTATIONS
    # -------------------------------

    def _create_issue(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Create a GitHub issue."""

        repo = cfg.get("repo")
        title = cfg.get("title")
        body = cfg.get("body", "")

        if not repo or not title:
            return {"error": "repo and title are required"}

        url = f"https://api.github.com/repos/{repo}/issues"

        headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
        }

        payload = {"title": title, "body": body}

        with httpx.Client(timeout=30) as client:
            res = client.post(url, json=payload, headers=headers)
            if res.status_code >= 300:
                return {"error": res.text}
            return res.json()

    def _create_pull_request(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Create a pull request."""

        repo = cfg.get("repo")
        title = cfg.get("title")
        head = cfg.get("head")
        base = cfg.get("base")

        if not repo or not title or not head or not base:
            return {"error": "repo, title, head, base are required"}

        url = f"https://api.github.com/repos/{repo}/pulls"

        headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
        }

        payload = {
            "title": title,
            "head": head,
            "base": base
        }

        with httpx.Client(timeout=30) as client:
            res = client.post(url, json=payload, headers=headers)
            if res.status_code >= 300:
                return {"error": res.text}
            return res.json()

    def _list_repos(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """List user repositories."""

        user = cfg.get("user")
        if not user:
            return {"error": "user is required"}

        url = f"https://api.github.com/users/{user}/repos"

        headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
        }

        with httpx.Client(timeout=30) as client:
            res = client.get(url, headers=headers)
            if res.status_code >= 300:
                return {"error": res.text}
            return res.json()
