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

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_timeout_seconds: float = Field(default=30, ge=1, le=120)
    openai_max_retries: int = Field(default=2, ge=0, le=3)
    openai_max_output_tokens: int = Field(default=1_200, ge=128, le=4_000)
    openai_max_evidence_items: int = Field(default=20, ge=1, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
