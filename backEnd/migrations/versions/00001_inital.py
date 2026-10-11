"""Legacy starter schema baseline, before authentication fields.

Revision ID: 0001_initial
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This baseline matches the original starter schema. Existing databases can
    # be stamped at this revision before applying 0002_production_auth.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_memberships_id", "memberships", ["id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_status", "memberships", ["status"])
    op.create_index("ix_memberships_expiry_date", "memberships", ["expiry_date"])

    op.create_table(
        "check_ins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_name", sa.String(length=120), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_check_ins_id", "check_ins", ["id"])
    op.create_index("ix_check_ins_user_id", "check_ins", ["user_id"])
    op.create_index("ix_check_ins_membership_id", "check_ins", ["membership_id"])
    op.create_index("ix_check_ins_checked_in_at", "check_ins", ["checked_in_at"])


def downgrade() -> None:
    op.drop_index("ix_check_ins_checked_in_at", table_name="check_ins")
    op.drop_index("ix_check_ins_membership_id", table_name="check_ins")
    op.drop_index("ix_check_ins_user_id", table_name="check_ins")
    op.drop_index("ix_check_ins_id", table_name="check_ins")
    op.drop_table("check_ins")
    op.drop_index("ix_memberships_expiry_date", table_name="memberships")
    op.drop_index("ix_memberships_status", table_name="memberships")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
