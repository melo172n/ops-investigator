from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
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

    loki_url: str = ""
    loki_bearer_token: SecretStr = SecretStr("")
    loki_tenant_id: str = ""
    loki_queries_by_service: dict[str, str] = Field(default_factory=dict)
    loki_timeout_seconds: float = Field(default=10, ge=1, le=60)
    loki_window_before_minutes: int = Field(default=15, ge=0, le=60)
    loki_window_after_minutes: int = Field(default=15, ge=0, le=60)
    loki_query_limit: int = Field(default=100, ge=1, le=1_000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_loki_window(self) -> "Settings":
        total_minutes = (
            self.loki_window_before_minutes + self.loki_window_after_minutes
        )
        if total_minutes > 60:
            raise ValueError("A janela total do Loki não pode exceder 60 minutos")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
