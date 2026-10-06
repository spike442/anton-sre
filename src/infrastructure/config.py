from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class ShellConfig(BaseModel):
    allowed_binaries: list[str]
    denied_patterns: list[str]


class LLMConfig(BaseModel):
    base_url: str
    model: str
    prompt_cache_key: str
    tools: list[dict[str, Any]]
    shell: ShellConfig
    secret_material_patterns: list[str]


class RepositoryConfig(BaseModel):
    url: str
    branch: str
    path: Path


class AgentConfig(BaseModel):
    name: str


class GitHubConfig(BaseModel):
    commit_author_name: str
    commit_author_email: str


class PrometheusConfig(BaseModel):
    url: str


class S3Config(BaseModel):
    endpoint: str
    region: str
    bucket: str
    prompt_prefix: str
    system_key: str
    context_key: str
    prompt_sha256: str
    access_key_id: str
    secret_access_key: str


class LimitsConfig(BaseModel):
    max_tool_calls: int
    max_tool_output_bytes: int


class DatabaseConfig(BaseModel):
    host: str
    port: int
    name: str
    user: str


class ApiConfig(BaseModel):
    allowed_origins: list[str]


class ReleaseConfig(BaseModel):
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    branch_prefix: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=[
            "/etc/anton/config/config.yaml",
            "/etc/anton/config/llm.yaml",
            "infra/config/config.yaml",
            "infra/config/llm.yaml",
        ],
        env_prefix="ANTON_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    llm: LLMConfig
    agent: AgentConfig
    repository: RepositoryConfig
    github: GitHubConfig
    prometheus: PrometheusConfig
    s3: S3Config
    limits: LimitsConfig
    database: DatabaseConfig
    api: ApiConfig
    release: ReleaseConfig
    database_password: str = Field(validation_alias="ANTON_DATABASE_PASSWORD")
    openai_api_key: str = Field(validation_alias=AliasChoices("ANTON_LLM_API_KEY", "OPENAI_API_KEY"))
    github_app_id: str = Field(validation_alias="ANTON_GITHUB_APP_ID")
    github_installation_id: str = Field(validation_alias="ANTON_GITHUB_INSTALLATION_ID")
    github_private_key: str = Field(validation_alias="ANTON_GITHUB_APP_PRIVATE_KEY")
    alert_token: str = Field(validation_alias="ANTON_ALERT_TOKEN")
    discord_webhook_url: str = Field(validation_alias="ANTON_DISCORD_WEBHOOK_URL")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls), file_secret_settings)

    @classmethod
    def load(cls) -> "Settings":
        return cls()

    @property
    def llm_base_url(self) -> str:
        return self.llm.base_url

    @property
    def agent_name(self) -> str:
        return self.agent.name

    @property
    def release_version(self) -> str:
        return self.release.version

    @property
    def release_branch_prefix(self) -> str:
        return self.release.branch_prefix

    @property
    def llm_model(self) -> str:
        return self.llm.model

    @property
    def llm_tools(self) -> list[dict[str, Any]]:
        return self.llm.tools

    @property
    def shell_allowed_binaries(self) -> list[str]:
        return self.llm.shell.allowed_binaries

    @property
    def shell_denied_patterns(self) -> list[str]:
        return self.llm.shell.denied_patterns

    @property
    def secret_material_patterns(self) -> list[str]:
        return self.llm.secret_material_patterns

    @property
    def prompt_cache_key(self) -> str:
        return self.llm.prompt_cache_key

    @property
    def github_owner(self) -> str:
        return self._github_repository_parts()[0]

    @property
    def github_repo(self) -> str:
        return self._github_repository_parts()[1]

    @property
    def commit_author_name(self) -> str:
        return self.github.commit_author_name

    @property
    def commit_author_email(self) -> str:
        return self.github.commit_author_email

    @property
    def repository_url(self) -> str:
        return self.repository.url

    def _github_repository_parts(self) -> tuple[str, str]:
        parsed = urlsplit(self.repository.url)
        path = parsed.path.strip("/").removesuffix(".git")
        parts = path.split("/")
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com" or len(parts) != 2:
            raise ValueError("repository.url must be a full github.com repository URL")
        return parts[0], parts[1]

    @property
    def default_branch(self) -> str:
        return self.repository.branch

    @property
    def repo_path(self) -> Path:
        return self.repository.path

    @property
    def prometheus_url(self) -> str:
        return self.prometheus.url

    @property
    def max_tool_calls(self) -> int:
        return self.limits.max_tool_calls

    @property
    def max_tool_output_bytes(self) -> int:
        return self.limits.max_tool_output_bytes

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{quote(self.database.user)}:{quote(self.database_password)}"
            f"@{self.database.host}:{self.database.port}/{quote(self.database.name)}"
        )

    @property
    def s3_endpoint(self) -> str:
        return self.s3.endpoint

    @property
    def s3_region(self) -> str:
        return self.s3.region

    @property
    def s3_bucket(self) -> str:
        return self.s3.bucket

    @property
    def s3_prompt_prefix(self) -> str:
        return self.s3.prompt_prefix

    @property
    def s3_system_key(self) -> str:
        return self.s3.system_key

    @property
    def s3_access_key_id(self) -> str:
        return self.s3.access_key_id

    @property
    def s3_secret_access_key(self) -> str:
        return self.s3.secret_access_key

    @property
    def prompt_sha256(self) -> str:
        return self.s3.prompt_sha256.lower()

    def require_llm(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError("ANTON_LLM_API_KEY or OPENAI_API_KEY is required")

    def require_github(self) -> None:
        missing = [name for name, value in {
            "ANTON_GITHUB_APP_ID": self.github_app_id,
            "ANTON_GITHUB_INSTALLATION_ID": self.github_installation_id,
            "ANTON_GITHUB_APP_PRIVATE_KEY": self.github_private_key,
        }.items() if not value]
        if missing:
            raise RuntimeError("Missing GitHub App settings: " + ", ".join(missing))
