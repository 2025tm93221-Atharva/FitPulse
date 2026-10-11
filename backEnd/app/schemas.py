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
