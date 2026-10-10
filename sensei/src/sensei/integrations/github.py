import httpx
from hive_common.github import GitHubAppAuth

from sensei.domain.models import PullRequest
from sensei.infrastructure.config import RepositoryConfig


class GitHubClient:
    """GitHub API client used by the polling loop."""

    def __init__(self, api_url: str, app_id: str, installation_id: str, private_key: str):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client = httpx.Client(
            base_url=api_url.rstrip("/"),
            headers=headers,
            timeout=30,
        )
        self.auth = GitHubAppAuth(self.client, api_url, app_id, installation_id, private_key)

    def list_open_pull_requests(self, repository: RepositoryConfig) -> list[PullRequest]:
        response = self.client.get(
            f"/repos/{repository.owner}/{repository.name}/pulls",
            headers=self.auth.headers(),
            params={"state": "open", "sort": "updated", "direction": "desc", "per_page": 100},
        )
        response.raise_for_status()
        return [
            PullRequest(
                owner=repository.owner,
                repository=repository.name,
                number=item["number"],
                base_sha=item["base"]["sha"],
                head_sha=item["head"]["sha"],
                clone_url=repository.clone_url,
                html_url=item.get("html_url", ""),
                updated_at=item.get("updated_at", ""),
                title=item.get("title", ""),
                author=(item.get("user") or {}).get("login", ""),
                head_ref=(item.get("head") or {}).get("ref", ""),
                labels=[label.get("name", "") for label in item.get("labels", [])],
            )
            for item in response.json()
        ]

    def is_mergeable(self, pull_request: PullRequest) -> bool:
        response = self.client.get(
            f"/repos/{pull_request.owner}/{pull_request.repository}/pulls/{pull_request.number}",
            headers=self.auth.headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("mergeable") is True and payload.get("mergeable_state") == "clean"

    def merge_pull_request(self, pull_request: PullRequest, merge_method: str) -> str:
        response = self.client.put(
            f"/repos/{pull_request.owner}/{pull_request.repository}/pulls/{pull_request.number}/merge",
            headers=self.auth.headers(),
            json={"sha": pull_request.head_sha, "merge_method": merge_method},
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("merged"):
            raise RuntimeError(result.get("message", "GitHub did not merge the pull request"))
        return str(result.get("sha", ""))

    def close(self) -> None:
        self.client.close()
