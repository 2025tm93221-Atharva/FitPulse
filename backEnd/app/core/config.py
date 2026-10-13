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
    public_app_url: str = "http://localhost:5173"
    mail_backend: str = "console"
    mail_from: str = "FIT PULSE <no-reply@example.invalid>"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    password_reset_token_expire_minutes: int = Field(default=30, ge=5, le=120)
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_claims_email: str | None = None

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
        if self.mail_backend not in {"console", "smtp"}:
            raise ValueError("MAIL_BACKEND must be either 'console' or 'smtp'")
        if environment in {"staging", "production"} and self.mail_backend == "console":
            # Console delivery is only acceptable for local development. Staging/prod reset links
            # must leave via a configured mail transport, never be emitted into application logs.
            raise ValueError("Staging/production requires MAIL_BACKEND=smtp for account recovery")
        if self.mail_backend == "smtp" and (not self.smtp_host or not self.mail_from):
            raise ValueError("SMTP mail delivery requires SMTP_HOST and MAIL_FROM")
        if environment in {"staging", "production"}:
            smtp_values = [self.smtp_host or "", self.smtp_username or "", self.smtp_password or ""]
            if any(value.lower().startswith(("change_me", "changeme", "replace-this")) for value in smtp_values if value):
                raise ValueError("Staging/production SMTP settings must not contain placeholder values")
            if environment == "production" and not self.public_app_url.lower().startswith("https://"):
                raise ValueError("Production PUBLIC_APP_URL must use HTTPS")
        vapid_values = [self.vapid_public_key, self.vapid_private_key, self.vapid_claims_email]
        if any(vapid_values) and not all(vapid_values):
            raise ValueError("VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, and VAPID_CLAIMS_EMAIL must be configured together")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be supplied together")
        if environment == "production":
            if "localhost" in self.cors_origins or "127.0.0.1" in self.cors_origins:
                raise ValueError("Production CORS_ORIGINS must not include localhost origins")
        return self


settings = Settings()
