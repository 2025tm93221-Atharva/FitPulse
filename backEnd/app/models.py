from datetime import datetime, date , timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backEnd.app.core.database import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    check_ins: Mapped[list["CheckIn"]] = relationship(
        back_populates="user"
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tier: Mapped[str] = mapped_column(
        String(40), nullable=False, default="basic"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    start_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    expiry_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="memberships"
    )
    check_ins: Mapped[list["CheckIn"]] = relationship(
        back_populates="membership"
    )


class CheckIn(Base):
    __tablename__ = "check_ins"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now,
        nullable=False, index=True
    )
    location_name: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    result: Mapped[str] = mapped_column(
        String(20), nullable=False, default="accepted"
    )

    user: Mapped["User"] = relationship(
        back_populates="check_ins"
    )
    membership: Mapped["Membership | None"] = relationship(
        back_populates="check_ins"
    )