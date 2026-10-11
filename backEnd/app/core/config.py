from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_DEVELOPMENT_SECRET = "dev-only-change-this-secret-before-deployment-8f2c"


class Settings(BaseSettings):
    app_name: str = "Fitness Membership API"
    environment: str = "development"
    database_url: str = "sqlite:///./fitness.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    secret_key: str = _DEVELOPMENT_SECRET
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    qr_token_expire_seconds: int = Field(default=60, ge=10, le=300)
    business_timezone: str = "UTC"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_runtime_configuration(self):
        try:
            ZoneInfo(self.business_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("BUSINESS_TIMEZONE must be a valid IANA timezone") from exc

        environment = self.environment.lower()
        if environment in {"staging", "production"}:
            secret = self.secret_key
            if secret == _DEVELOPMENT_SECRET or secret.lower().startswith(("replace-this", "change_me", "changeme")) or len(secret) < 32:
                raise ValueError("Staging/production requires a unique SECRET_KEY of at least 32 characters")
        if environment == "production":
            if "localhost" in self.cors_origins or "127.0.0.1" in self.cors_origins:
                raise ValueError("Production CORS_ORIGINS must not include localhost origins")
        return self


settings = Settings()
