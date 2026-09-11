from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: SecretStr = SecretStr("")

    zabbix_webhook_secret: SecretStr

    chatwoot_enabled: bool = False
    chatwoot_url: str = ""
    chatwoot_api_token: SecretStr = SecretStr("")
    chatwoot_account_id: int = 0
    chatwoot_operations_conversation_id: int = 0
    chatwoot_max_attempts: int = Field(default=3, ge=1, le=5)
    chatwoot_retry_base_delay_seconds: float = Field(
        default=0.5,
        ge=0,
        le=5,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
