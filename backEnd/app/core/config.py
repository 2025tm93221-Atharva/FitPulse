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
    def validate_production_secrets(self):
        if self.environment.lower() == "production":
            if (self.secret_key == _DEVELOPMENT_SECRET or self.secret_key.lower().startswith("replace-this") or len(self.secret_key) < 32):
                raise ValueError("Production requires a unique SECRET_KEY of at least 32 characters")
            if "localhost" in self.cors_origins or "127.0.0.1" in self.cors_origins:
                raise ValueError("Production CORS_ORIGINS must not include localhost origins")
        return self


settings = Settings()