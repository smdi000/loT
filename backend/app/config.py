from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are loaded only from environment/.env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Qmzg Training Backend"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://qmzg:qmzg_local_dev@postgres:5432/qmzg"
    sql_echo: bool = False

    tuya_access_id: str = Field(default="", validation_alias="TUYA_ACCESS_ID")
    tuya_access_secret: str = Field(default="", validation_alias="TUYA_ACCESS_SECRET")
    tuya_pulsar_url: str = Field(default="", validation_alias="TUYA_PULSAR_URL")
    tuya_pulsar_topic: str = Field(default="", validation_alias="TUYA_PULSAR_TOPIC")
    tuya_pulsar_subscription: str = Field(
        default="", validation_alias="TUYA_PULSAR_SUBSCRIPTION"
    )
    jwt_secret: str = Field(default="", validation_alias="JWT_SECRET")
    jwt_access_token_expire_minutes: int = Field(
        default=60,
        validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        ge=5,
        le=24 * 60,
    )

    @property
    def tuya_pulsar_configured(self) -> bool:
        return bool(
            self.tuya_access_id
            and self.tuya_access_secret
            and self.tuya_pulsar_url
            and self.tuya_pulsar_topic
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
