from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class AppConfig(BaseModel):
    name: str
    version: str


class LoggingConfig(BaseModel):
    level: str


class ReviewConfig(BaseModel):
    merge_enabled: bool
    merge_method: str
    allowed_risk_levels: set[str]
    allowed_confidence_levels: set[str]
    command_timeout_seconds: int
    max_diff_bytes: int
    max_tool_calls: int
    max_tool_output_bytes: int
    workspace_root: Path
    poll_interval_seconds: int


class LLMConfig(BaseModel):
    base_url: str
    model: str
    prompt_cache_key: str


class RepositoryToolConfig(BaseModel):
    name: str
    command: str
    description: str
    parameters: dict[str, Any]


class RepositoryConfig(BaseModel):
    owner: str
    name: str
    clone_url: str
    clone_depth: int
    tools: list[RepositoryToolConfig]


class GitHubConfig(BaseModel):
    api_url: str


class S3Config(BaseModel):
    bucket: str
    prefix: str
    root_context_object_name: str
    object_name: str
    action_prompt_prefix: str
    endpoint_url: str
    region: str


class DatabaseConfig(BaseModel):
    host: str
    port: int
    name: str
    user: str


class ApiConfig(BaseModel):
    allowed_origins: list[str]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=[
            "/etc/sensei/config.yaml",
            "/etc/sensei/llm.yaml",
            "/etc/sensei/repositories.yaml",
            "sensei/infra/config/config.yaml",
            "sensei/infra/config/llm.yaml",
            "sensei/infra/config/repositories.yaml",
            "infra/config/config.yaml",
            "infra/config/llm.yaml",
            "infra/config/repositories.yaml",
        ],
        env_prefix="SENSEI_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppConfig
    logging: LoggingConfig
    review: ReviewConfig
    llm: LLMConfig
    repositories: list[RepositoryConfig]
    github: GitHubConfig
    s3: S3Config
    database: DatabaseConfig
    api: ApiConfig
    github_app_id: str = Field(min_length=1, validation_alias="SENSEI_GITHUB_APP_ID")
    github_installation_id: str = Field(min_length=1, validation_alias="SENSEI_GITHUB_INSTALLATION_ID")
    github_private_key: str = Field(min_length=1, validation_alias="SENSEI_GITHUB_APP_PRIVATE_KEY")
    s3_access_key_id: str = Field(min_length=1, validation_alias="SENSEI_S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(min_length=1, validation_alias="SENSEI_S3_SECRET_ACCESS_KEY")
    openai_api_key: str = Field(min_length=1, validation_alias="SENSEI_LLM_API_KEY")
    control_token: str = Field(min_length=1, validation_alias="SENSEI_CONTROL_TOKEN")
    database_password: str = Field(min_length=1, validation_alias="SENSEI_DATABASE_PASSWORD")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings, YamlConfigSettingsSource(settings_cls), file_secret_settings

    @classmethod
    def load(cls) -> "Settings":
        return cls()

    @property
    def version(self) -> str:
        return self.app.version

    @property
    def agent_name(self) -> str:
        return self.app.name

    @property
    def poll_interval_seconds(self) -> int:
        return self.review.poll_interval_seconds

    @property
    def workspace_root(self) -> Path:
        return self.review.workspace_root

    @property
    def command_timeout_seconds(self) -> int:
        return self.review.command_timeout_seconds

    @property
    def max_diff_bytes(self) -> int:
        return self.review.max_diff_bytes

    @property
    def max_tool_calls(self) -> int:
        return self.review.max_tool_calls

    @property
    def max_tool_output_bytes(self) -> int:
        return self.review.max_tool_output_bytes

    @property
    def llm_base_url(self) -> str:
        return self.llm.base_url

    @property
    def llm_model(self) -> str:
        return self.llm.model

    @property
    def prompt_cache_key(self) -> str:
        return self.llm.prompt_cache_key

    @property
    def merge_enabled(self) -> bool:
        return self.review.merge_enabled

    @property
    def merge_method(self) -> str:
        return self.review.merge_method

    @property
    def allowed_risk_levels(self) -> set[str]:
        return self.review.allowed_risk_levels

    @property
    def allowed_confidence_levels(self) -> set[str]:
        return self.review.allowed_confidence_levels

    @property
    def github_api_url(self) -> str:
        return self.github.api_url

    @property
    def s3_bucket(self) -> str:
        return self.s3.bucket

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.database.user}:{self.database_password}"
            f"@{self.database.host}:{self.database.port}/{self.database.name}"
        )

    @property
    def s3_prefix(self) -> str:
        return self.s3.prefix

    @property
    def s3_object_name(self) -> str:
        return self.s3.object_name

    @property
    def root_context_object_name(self) -> str:
        return self.s3.root_context_object_name

    @property
    def s3_endpoint_url(self) -> str:
        return self.s3.endpoint_url

    @property
    def s3_region(self) -> str:
        return self.s3.region

    @property
    def action_prompt_prefix(self) -> str:
        return self.s3.action_prompt_prefix
