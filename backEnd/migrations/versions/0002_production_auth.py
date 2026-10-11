"""Add authentication, roles, and one-use gym pass IDs.

Revision ID: 0002_production_auth
Revises: 0001_initial
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_production_auth"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable first so this migration works on both blank and already-populated
    # databases. Existing users receive an empty password field and must have
    # a password set by an operator before they can sign in.
    op.add_column("users", sa.Column("hashed_password", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("role", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column("check_ins", sa.Column("qr_jti", sa.String(length=64), nullable=True))

    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
    op.execute("UPDATE users SET role = 'member' WHERE role IS NULL")
    op.execute("UPDATE users SET is_active = true WHERE is_active IS NULL")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("hashed_password", existing_type=sa.String(length=255), nullable=False)
        batch_op.alter_column("role", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("is_active", existing_type=sa.Boolean(), nullable=False)
    op.create_index("ix_users_role", "users", ["role"])
    with op.batch_alter_table("check_ins") as batch_op:
        batch_op.create_unique_constraint("uq_check_ins_qr_jti", ["qr_jti"])


def downgrade() -> None:
    with op.batch_alter_table("check_ins") as batch_op:
        batch_op.drop_constraint("uq_check_ins_qr_jti", type_="unique")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("check_ins", "qr_jti")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("role")
        batch_op.drop_column("hashed_password")
