import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_staging_rejects_placeholder_secret():
    with pytest.raises(ValidationError):
        Settings(environment="staging", secret_key="CHANGE_ME_USE_A_UNIQUE_RANDOM_SECRET_AT_LEAST_48_CHARACTERS")


def test_staging_accepts_unique_secret_and_iana_timezone():
    settings = Settings(
        environment="staging",
        secret_key="a-test-only-random-secret-long-enough-for-staging-123456789",
        business_timezone="Asia/Kolkata",
        mail_backend="smtp",
        mail_from="FitPulse Test <test@example.com>",
        smtp_host="smtp.example.com",
    )
    assert settings.business_timezone == "Asia/Kolkata"


def test_invalid_business_timezone_is_rejected():
    with pytest.raises(ValidationError):
        Settings(business_timezone="Moon/Base")


def test_production_rejects_local_cors_origin():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            secret_key="a-production-secret-that-is-long-enough-and-not-default-123",
            cors_origins="https://fitness.example.com,http://localhost:5173",
            public_app_url="https://fitness.example.com",
            mail_backend="smtp",
            mail_from="FitPulse Test <test@example.com>",
            smtp_host="smtp.example.com",
        )
