import base64
from datetime import datetime, timedelta, timezone
import secrets
import subprocess
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from infrastructure.config import Settings


class GitHubApp:
    _sync_lock = threading.Lock()

    def __init__(self, settings: Settings):
        settings.require_github()
        self.settings = settings
        self.client = httpx.Client(timeout=30)

    def close(self) -> None:
        self.client.close()

    def _jwt(self) -> str:
        now = datetime.now(timezone.utc)
        claims = {"iat": int((now - timedelta(seconds=30)).timestamp()), "exp": int((now + timedelta(minutes=9)).timestamp()), "iss": self.settings.github_app_id}
        return jwt.encode(claims, self.settings.github_private_key, algorithm="RS256")

    def _token(self) -> str:
        response = self.client.post(f"https://api.github.com/app/installations/{self.settings.github_installation_id}/access_tokens",
                                    headers={"Authorization": f"Bearer {self._jwt()}", "Accept": "application/vnd.github+json"})
        response.raise_for_status()
        return response.json()["token"]

    def _request(self, method: str, path: str, **kwargs):
        response = self.client.request(method, f"https://api.github.com{path}",
                                       headers={"Authorization": f"Bearer {self._token()}", "Accept": "application/vnd.github+json"}, **kwargs)
        response.raise_for_status()
        return response.json()

    def sync_repository(self) -> dict[str, str]:
        """Synchronize the public repository checkout without GitHub API credentials."""
        path = self.settings.repo_path
        path.parent.mkdir(parents=True, exist_ok=True)
        remote = self.settings.repository_url
        branch = self.settings.default_branch
        with self._sync_lock:
            if (path / ".git").is_dir():
                self._git(["-C", str(path), "remote", "set-url", "origin", remote])
                self._git(["-C", str(path), "fetch", "--prune", "origin", branch])
                self._git(["-C", str(path), "checkout", "-B", branch, f"origin/{branch}"])
                self._git(["-C", str(path), "reset", "--hard", f"origin/{branch}"])
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._git(["clone", "--single-branch", "--branch", branch, remote, str(path)])
            commit = self._git(["-C", str(path), "rev-parse", "HEAD"]).strip()
        return {"path": str(path), "branch": branch, "commit": commit}

    @staticmethod
    def _git(arguments: list[str]) -> str:
        result = subprocess.run(["git", *arguments], capture_output=True, text=True,
                                timeout=60, check=False)
        if result.returncode:
            raise RuntimeError(f"git synchronization failed: {result.stderr[-1000:]}")
        return result.stdout

    def create_pull_request(self, changes: list[Any], title: str, body: str,
                            labels: list[str] | None = None) -> dict:
        owner, repo, branch = self.settings.github_owner, self.settings.github_repo, self.settings.default_branch
        with self._sync_lock:
            new_branch = self._push_changes(owner, repo, branch, changes, title)
        pull_request = self._open_pull_request(owner, repo, new_branch, branch, title, body)
        if labels:
            self._add_labels(pull_request["number"], labels)
        return pull_request

    def _push_changes(self, owner: str, repo: str, base_branch: str,
                      changes: list[Any], title: str) -> str:
        branch = f"{self.settings.release_branch_prefix}/{self.settings.release_version}/{secrets.token_hex(6)}"
        path = self.settings.repo_path
        remote = f"git@github-bot:{owner}/{repo}.git"
        self._git(["-C", str(path), "remote", "set-url", "origin", remote])
        self._git(["-C", str(path), "checkout", "-B", branch, base_branch])
        for change in changes:
            target = (path / change.file_path).resolve()
            if path.resolve() not in target.parents:
                raise ValueError(f"change path escapes repository: {change.file_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.content, encoding="utf-8")
        self._git(["-C", str(path), "add", "--", *(change.file_path for change in changes)])
        self._git(["-C", str(path), "diff", "--cached", "--check"])
        self._git(["-C", str(path), "config", "user.name", self.settings.commit_author_name])
        self._git(["-C", str(path), "config", "user.email", self.settings.commit_author_email])
        self._git(["-C", str(path), "commit", "-m", title])
        self._git(["-C", str(path), "push", "--set-upstream", "origin", branch])
        return branch

    def _open_pull_request(self, owner: str, repo: str, head: str, base: str,
                           title: str, body: str) -> dict:
        return self._request("POST", f"/repos/{owner}/{repo}/pulls",
                             json={"title": title, "head": head, "base": base, "body": body})

    def _add_labels(self, number: int, labels: list[str]) -> None:
        owner, repo = self.settings.github_owner, self.settings.github_repo
        for label in labels:
            try:
                self._request("POST", f"/repos/{owner}/{repo}/labels",
                              json={"name": label, "color": "1d76db",
                                    "description": f"Anton {label} classification"})
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 422:
                    raise
        self._request("POST", f"/repos/{owner}/{repo}/issues/{number}/labels",
                      json={"labels": labels})

    def read(self, action: str, path: str | None = None, number: int | None = None,
             limit: int = 10) -> dict:
        """Read repository state without exposing secret-looking files."""
        owner, repo = self.settings.github_owner, self.settings.github_repo
        limit = max(1, min(limit, 20))
        if action == "file":
            if not path or any(part in path.lower() for part in ("secret", ".sops", "private", "token", "password")):
                raise ValueError("refusing to read a secret-looking repository path")
            result = self._request("GET", f"/repos/{owner}/{repo}/contents/{quote(path, safe='/')}")
            content = base64.b64decode(result["content"]).decode("utf-8", errors="replace")
            return {"path": path, "content": content[-12000:]}
        if action == "commits":
            return {"commits": self._request("GET", f"/repos/{owner}/{repo}/commits", params={"per_page": limit})}
        if action == "pull_request":
            if not number:
                raise ValueError("number is required for pull_request")
            return {"pull_request": self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")}
        raise ValueError("action must be file, commits, or pull_request")
