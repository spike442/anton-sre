import hashlib
from typing import Any

import boto3

from infrastructure.config import Settings


class PromptStore:
    def __init__(self, settings: Settings):
        if not settings.s3_bucket or not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise RuntimeError("S3 prompt store configuration is incomplete")
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        self._system_prompt = self._load_system_prompt()
        self._context = self.text(settings.s3.context_key)
        self._action_prompts = {
            "investigate": self.text("actions/investigate.md"),
            "replay": self.text("actions/replay.md"),
        }
        self._action_prompts.update({
            name: self.text(f"actions/{name}.md")
            for tool in settings.llm_tools
            if (name := tool.get("name"))
        })

    def close(self) -> None:
        self.client.close()

    def _key(self, key: str) -> str:
        return f"{self.settings.s3_prompt_prefix.rstrip('/')}/{key.lstrip('/')}"

    def text(self, key: str) -> str:
        response = self.client.get_object(Bucket=self.settings.s3_bucket, Key=self._key(key))
        if response.get("ContentLength", 0) > 100_000:
            raise RuntimeError(f"prompt is too large: {key}")
        content = response["Body"].read(100_001).decode("utf-8")
        if len(content.encode()) > 100_000:
            raise RuntimeError(f"prompt is too large: {key}")
        return content

    def system(self) -> str:
        return self._system_prompt

    def context(self) -> str:
        return self._context

    def _load_system_prompt(self) -> str:
        content = self.text(self.settings.s3_system_key)
        if self.settings.prompt_sha256:
            digest = hashlib.sha256(content.encode()).hexdigest()
            if digest != self.settings.prompt_sha256:
                raise RuntimeError("system prompt checksum does not match ANTON_PROMPT_SHA256")
        return content

    def action(self, name: str) -> str:
        try:
            return self._action_prompts[name]
        except KeyError as exc:
            raise RuntimeError(f"missing prompt for action: {name}") from exc
