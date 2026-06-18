"""GitHub plugin — github capability.

Wraps PyGithub for repository operations.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

import git
from github import Github
from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class GitHubPlugin(BasePlugin):
    """GitHub plugin: clone, list_repos, get_repo_info, create_issue, create_pr."""

    spec = BridgeSpec(
        name="github",
        version="0.1.0",
        capabilities=["github"],
        description="GitHub operations via PyGithub + gitpython",
    )
    plugin_spec = PluginSpec(
        name="github",
        version="0.1.0",
        capabilities=["github"],
        priority=10,
        description="GitHub: clone, list, PRs, issues",
    )

    def __init__(self) -> None:
        self.client: Github | None = None

    async def initialize(self) -> None:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            logger.warning("GITHUB_TOKEN not set — github plugin will be read-only and may fail")
        self.client = Github(token) if token else Github()

    def methods(self) -> list[str]:
        return ["clone", "list_repos", "get_repo_info", "create_issue", "create_pull_request", "list_commits"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        assert self.client is not None, "github plugin not initialized"
        if method == "clone":
            return await self._clone(**params)
        if method == "list_repos":
            return await self._list_repos(**params)
        if method == "get_repo_info":
            return await self._get_repo_info(**params)
        if method == "create_issue":
            return await self._create_issue(**params)
        if method == "create_pull_request":
            return await self._create_pull_request(**params)
        if method == "list_commits":
            return await self._list_commits(**params)
        raise ValueError(f"unknown method: {method}")

    async def _clone(self, repo: str, dest: str | None = None) -> dict[str, Any]:
        """Clone a repo. `repo` is 'owner/name'."""
        dest = dest or tempfile.mkdtemp(prefix="alterego-clone-")
        token = os.environ.get("GITHUB_TOKEN", "")
        url = f"https://github.com/{repo}.git"
        if token:
            url = f"https://{token}@github.com/{repo}.git"
        git.Repo.clone_from(url, dest)
        logger.info(f"cloned {repo} → {dest}")
        return {"path": dest, "repo": repo}

    async def _list_repos(self, owner: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if owner:
            user = self.client.get_user(owner)
            repos = user.get_repos()
        else:
            repos = self.client.get_user().get_repos()
        return [
            {"name": r.full_name, "stars": r.stargazers_count, "url": r.html_url, "private": r.private}
            for r in list(repos)[:limit]
        ]

    async def _get_repo_info(self, repo: str) -> dict[str, Any]:
        r = self.client.get_repo(repo)
        return {
            "name": r.full_name,
            "stars": r.stargazers_count,
            "forks": r.forks_count,
            "description": r.description,
            "default_branch": r.default_branch,
            "url": r.html_url,
            "open_issues": r.open_issues_count,
        }

    async def _create_issue(self, repo: str, title: str, body: str = "") -> dict[str, Any]:
        r = self.client.get_repo(repo)
        issue = r.create_issue(title=title, body=body)
        return {"number": issue.number, "url": issue.html_url}

    async def _create_pull_request(
        self, repo: str, title: str, head: str, base: str = "main", body: str = ""
    ) -> dict[str, Any]:
        r = self.client.get_repo(repo)
        pr = r.create_pull(title=title, body=body, head=head, base=base)
        return {"number": pr.number, "url": pr.html_url}

    async def _list_commits(self, repo: str, limit: int = 10) -> list[dict[str, Any]]:
        r = self.client.get_repo(repo)
        commits = list(r.get_commits())[:limit]
        return [
            {"sha": c.sha[:8], "message": c.commit.message[:100], "author": c.commit.author.name}
            for c in commits
        ]

    async def health(self) -> bool:
        return self.client is not None

    async def shutdown(self) -> None:
        pass
