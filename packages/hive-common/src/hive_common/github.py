"""Shared GitHub App authentication for Hive services."""

from datetime import UTC, datetime, timedelta

import httpx
import jwt


class GitHubAppAuth:
    """Issue and cache an installation token for a GitHub App."""

    def __init__(
        self,
        client: httpx.Client,
        api_url: str,
        app_id: str,
        installation_id: str,
        private_key: str,
    ) -> None:
        self._client = client
        self._api_url = api_url.rstrip("/")
        self._app_id = app_id
        self._installation_id = installation_id
        self._private_key = private_key
        self._token = ""
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)

    def headers(self) -> dict[str, str]:
        """Return headers authenticated as the installed GitHub App."""
        return {"Authorization": f"Bearer {self._installation_token()}"}

    def _installation_token(self) -> str:
        now = datetime.now(UTC)
        if self._token and now < self._token_expires_at - timedelta(minutes=1):
            return self._token
        if not all((self._app_id, self._installation_id, self._private_key)):
            raise RuntimeError("GitHub App credentials are not configured")

        claims = {
            "iat": int((now - timedelta(seconds=30)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": self._app_id,
        }
        app_jwt = jwt.encode(claims, self._private_key, algorithm="RS256")
        response = self._client.post(
            f"{self._api_url}/app/installations/{self._installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {app_jwt}"},
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["token"]
        self._token_expires_at = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
        return self._token
