from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("full_name must not be blank")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    role: Literal["member", "staff", "admin"]
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserRead


class MembershipCreate(BaseModel):
    user_id: int = Field(gt=0)
    tier: str = Field(default="basic", min_length=1, max_length=40)
    status: Literal["pending", "active"] = "pending"
    start_date: date
    expiry_date: date


class MembershipStatusUpdate(BaseModel):
    status: Literal["active", "frozen", "cancelled", "expired"]


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    tier: str
    status: str
    start_date: date
    expiry_date: date
    created_at: datetime


class QRTokenResponse(BaseModel):
    qr_token: str
    token_type: Literal["gym_checkin"] = "gym_checkin"
    membership_id: int
    expires_at: datetime


class ScannerQRRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qr_token: str = Field(min_length=1, max_length=4096)


class CheckInValidateRequest(BaseModel):
    qr_token: str = Field(min_length=1, max_length=4096)
    location_name: str = Field(min_length=1, max_length=120)

    @field_validator("location_name")
    @classmethod
    def trim_location(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("location_name must not be blank")
        return value


class CheckInRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    membership_id: int | None
    checked_in_at: datetime
    location_name: str | None
    result: str
    scanner_device_id: int | None = None


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("full_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("full_name must not be blank")
        return value


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordResetRequestResponse(BaseModel):
    message: str
    # Never present outside development; enables local recovery-flow acceptance tests.
    debug_reset_token: str | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    body: str
    category: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class PrivacyPreferencesRead(BaseModel):
    analytics_consent: bool = False
    marketing_consent: bool = False
    consent_version: str = "v1"
    updated_at: datetime | None = None


class PrivacyPreferencesUpdate(BaseModel):
    analytics_consent: bool = False
    marketing_consent: bool = False


class SupportTicketCreate(BaseModel):
    category: Literal["access", "membership", "billing", "technical", "privacy", "other"] = "other"
    subject: str = Field(min_length=4, max_length=140)
    message: str = Field(min_length=10, max_length=3000)

    @field_validator("subject", "message")
    @classmethod
    def trim_ticket_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value


class SupportTicketStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]
    staff_response: str | None = Field(default=None, max_length=3000)

    @field_validator("staff_response")
    @classmethod
    def trim_staff_response(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SupportTicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    category: str
    subject: str
    message: str
    status: str
    staff_response: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
