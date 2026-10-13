from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    check_ins: Mapped[list["CheckIn"]] = relationship(back_populates="user")


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(40), nullable=False, default="basic")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    freeze_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    freeze_until_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    check_ins: Mapped[list["CheckIn"]] = relationship(back_populates="membership")


class ScannerDevice(Base):
    """A trusted physical scanner; the raw API key is never persisted."""

    __tablename__ = "scanner_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    key_id: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    check_ins: Mapped[list["CheckIn"]] = relationship(back_populates="scanner_device")


class CheckIn(Base):
    __tablename__ = "check_ins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True, index=True
    )
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    location_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="accepted")
    # One-time QR tokens are recorded here to prevent replay. NULL is allowed for legacy/manual entries.
    qr_jti: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    scanner_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("scanner_devices.id", ondelete="SET NULL"), nullable=True, index=True
    )

    user: Mapped["User"] = relationship(back_populates="check_ins")
    membership: Mapped["Membership | None"] = relationship(back_populates="check_ins")
    scanner_device: Mapped["ScannerDevice | None"] = relationship(back_populates="check_ins")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserPrivacyPreferences(Base):
    __tablename__ = "user_privacy_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    analytics_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_version: Mapped[str] = mapped_column(String(24), nullable=False, default="v1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    subject: Mapped[str] = mapped_column(String(140), nullable=False)
    message: Mapped[str] = mapped_column(String(3000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    staff_response: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    instructor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    class_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    location_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    waitlist_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    cancellation_cutoff_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled", index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    bookings: Mapped[list["ClassBooking"]] = relationship(back_populates="class_session", cascade="all, delete-orphan")


class ClassBooking(Base):
    __tablename__ = "class_bookings"
    __table_args__ = (UniqueConstraint("class_session_id", "user_id", name="uq_class_booking_session_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked", index=True)
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waitlist_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    class_session: Mapped["ClassSession"] = relationship(back_populates="bookings")
    user: Mapped["User"] = relationship()
    reminders: Mapped[list["ClassReminder"]] = relationship(back_populates="booking", cascade="all, delete-orphan")


class ClassReminder(Base):
    __tablename__ = "class_reminders"
    __table_args__ = (UniqueConstraint("booking_id", "kind", name="uq_class_reminder_booking_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("class_bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    booking: Mapped["ClassBooking"] = relationship(back_populates="reminders")


class MembershipRenewalRequest(Base):
    __tablename__ = "membership_renewal_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    renewal_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
