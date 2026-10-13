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
    freeze_start_date: date | None = None
    freeze_until_date: date | None = None
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


class ClassSessionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)
    instructor_name: str = Field(min_length=1, max_length=120)
    class_type: str = Field(min_length=2, max_length=60)
    location_name: str = Field(min_length=1, max_length=120)
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(default=20, ge=1, le=500)
    waitlist_limit: int = Field(default=10, ge=0, le=500)
    cancellation_cutoff_minutes: int = Field(default=120, ge=0, le=1440)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime must include a timezone offset")
        return value

    @field_validator("title", "instructor_name", "class_type", "location_name")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value


class ClassSessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    instructor_name: str | None = Field(default=None, min_length=1, max_length=120)
    class_type: str | None = Field(default=None, min_length=2, max_length=60)
    location_name: str | None = Field(default=None, min_length=1, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=500)
    waitlist_limit: int | None = Field(default=None, ge=0, le=500)
    cancellation_cutoff_minutes: int | None = Field(default=None, ge=0, le=1440)
    status: Literal["scheduled", "cancelled"] | None = None

    @field_validator("title", "instructor_name", "class_type", "location_name")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value


class ClassSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    instructor_name: str
    class_type: str
    location_name: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    waitlist_limit: int
    cancellation_cutoff_minutes: int
    status: str
    created_at: datetime
    booked_count: int = 0
    available_spots: int = 0
    waitlist_count: int = 0


class ClassBookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    class_session_id: int
    user_id: int
    status: str
    booked_at: datetime | None
    waitlist_joined_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    waitlist_position: int | None = None
    class_session: ClassSessionRead


class MembershipFreezeRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=30)


class MembershipRenewalCreate(BaseModel):
    renewal_days: Literal[30, 90, 180, 365] = 365


class MembershipRenewalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membership_id: int
    user_id: int
    renewal_days: int
    status: Literal["pending", "approved", "rejected", "cancelled"]
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    created_at: datetime


class MembershipRenewalReview(BaseModel):
    status: Literal["approved", "rejected"]


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=12, max_length=2048)
    p256dh: str = Field(min_length=16, max_length=255)
    auth: str = Field(min_length=8, max_length=255)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Push endpoint must be an HTTPS URL")
        return value


class PushPublicKeyRead(BaseModel):
    enabled: bool
    public_key: str | None = None


class PushSubscriptionRead(BaseModel):
    id: int
    created_at: datetime
