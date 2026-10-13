"""V2 classes, bookings, reminders, membership self-service and push subscriptions.

Revision ID: 0005_v2_classes_self_service
Revises: 0004_v1_completion
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_v2_classes_self_service"
down_revision: Union[str, None] = "0004_v1_completion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.add_column(sa.Column("freeze_start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("freeze_until_date", sa.Date(), nullable=True))

    op.create_table(
        "class_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("instructor_name", sa.String(120), nullable=False),
        sa.Column("class_type", sa.String(60), nullable=False),
        sa.Column("location_name", sa.String(120), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("waitlist_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("cancellation_cutoff_minutes", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("title", "class_type", "location_name", "starts_at", "status"):
        op.create_index(f"ix_class_sessions_{column}", "class_sessions", [column])
    op.create_index("ix_class_sessions_id", "class_sessions", ["id"])

    op.create_table(
        "class_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="booked"),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waitlist_joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["class_session_id"], ["class_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("class_session_id", "user_id", name="uq_class_booking_session_user"),
    )
    for column in ("id", "class_session_id", "user_id", "status", "waitlist_joined_at"):
        op.create_index(f"ix_class_bookings_{column}", "class_bookings", [column])

    op.create_table(
        "class_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["class_bookings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("booking_id", "kind", name="uq_class_reminder_booking_kind"),
    )
    for column in ("id", "booking_id", "scheduled_at", "status"):
        op.create_index(f"ix_class_reminders_{column}", "class_reminders", [column])

    op.create_table(
        "membership_renewal_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("renewal_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("id", "membership_id", "user_id", "status"):
        op.create_index(f"ix_membership_renewal_requests_{column}", "membership_renewal_requests", [column])

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )
    op.create_index("ix_push_subscriptions_id", "push_subscriptions", ["id"])
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    for column in ("status", "user_id", "membership_id", "id"):
        op.drop_index(f"ix_membership_renewal_requests_{column}", table_name="membership_renewal_requests")
    op.drop_table("membership_renewal_requests")
    for column in ("status", "scheduled_at", "booking_id", "id"):
        op.drop_index(f"ix_class_reminders_{column}", table_name="class_reminders")
    op.drop_table("class_reminders")
    for column in ("waitlist_joined_at", "status", "user_id", "class_session_id", "id"):
        op.drop_index(f"ix_class_bookings_{column}", table_name="class_bookings")
    op.drop_table("class_bookings")
    for column in ("id", "status", "starts_at", "location_name", "class_type", "title"):
        op.drop_index(f"ix_class_sessions_{column}", table_name="class_sessions")
    op.drop_table("class_sessions")
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_column("freeze_until_date")
        batch_op.drop_column("freeze_start_date")
