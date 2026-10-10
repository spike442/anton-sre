from domain import AgentConfig
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class LoggingConfig(BaseModel):
    level: str


class HealthConfig(BaseModel):
    timeout_seconds: float


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
            "/etc/hive/config.yaml",
            "hive/infra/config/config.yaml",
            "infra/config/config.yaml",
        ],
        env_prefix="HIVE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    logging: LoggingConfig
    health: HealthConfig
    agents: list[AgentConfig]
    database: DatabaseConfig
    api: ApiConfig
    control_token: str = Field(min_length=1, validation_alias="HIVE_CONTROL_TOKEN")
    database_password: str = Field(min_length=1, validation_alias="HIVE_DATABASE_PASSWORD")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls), file_secret_settings)

    @classmethod
    def load(cls) -> "Settings":
        return cls()

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.database.user}:{self.database_password}"
            f"@{self.database.host}:{self.database.port}/{self.database.name}"
        )
