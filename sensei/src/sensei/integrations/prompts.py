import hashlib
from dataclasses import dataclass
from typing import Any

import boto3


@dataclass
class _CachedObject:
    text: str
    etag: str


class PromptStore:
    """Caches S3 prompt bodies and reloads them when their ETags change."""

    def __init__(self, settings):
        self.bucket = settings.s3_bucket
        self.context_prefix = settings.s3_prefix.strip("/")
        self.root_context_object_name = settings.root_context_object_name
        self.context_object_name = settings.s3_object_name
        self.action_prompt_prefix = settings.action_prompt_prefix.strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        self._objects: dict[str, _CachedObject] = {}

    def context(self, project: str) -> str:
        root_key = f"{self.context_prefix}/{self.root_context_object_name}"
        project_context_key = self._project_key(project, self.context_object_name)
        root = self._load(root_key)
        project_context = self._load(project_context_key)
        return f"{root.text}\n\n{project_context.text}"

    def action(self, project: str) -> str:
        key = f"{self.context_prefix}/{project}/{self.action_prompt_prefix}/review.md"
        return self._load(key).text

    def version(self, project: str) -> str:
        keys = (
            f"{self.context_prefix}/{self.root_context_object_name}",
            self._project_key(project, self.context_object_name),
            f"{self.context_prefix}/{project}/{self.action_prompt_prefix}/review.md",
        )
        for key in keys:
            self._load(key)
        return self._version(project, *keys)

    def _project_key(self, project: str, object_name: str) -> str:
        return f"{self.context_prefix}/{project}/{object_name}"

    def _load(self, key: str) -> _CachedObject:
        cached = self._objects.get(key)
        metadata = self.client.head_object(Bucket=self.bucket, Key=key)
        etag = str(metadata.get("ETag", "")).strip('"')
        if cached is not None and cached.etag == etag:
            return cached

        response: Any = self.client.get_object(Bucket=self.bucket, Key=key)
        text = response["Body"].read().decode("utf-8")
        loaded = _CachedObject(
            text=text,
            etag=etag,
        )
        self._objects[key] = loaded
        return loaded

    def _version(self, project: str, *keys: str) -> str:
        identity = "|".join([project, *(f"{key}:{self._objects[key].etag}" for key in keys)])
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]

    def close(self) -> None:
        self.client.close()
