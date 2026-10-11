"""Add trusted scanner devices and scanner attribution to check-ins.

Revision ID: 0003_scanner_devices
Revises: 0002_production_auth
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_scanner_devices"
down_revision: Union[str, None] = "0002_production_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scanner_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location_name", sa.String(length=120), nullable=False),
        sa.Column("key_id", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scanner_devices_id", "scanner_devices", ["id"])
    op.create_index("ix_scanner_devices_location_name", "scanner_devices", ["location_name"])
    op.create_index("ix_scanner_devices_key_id", "scanner_devices", ["key_id"], unique=True)
    with op.batch_alter_table("check_ins") as batch_op:
        batch_op.add_column(sa.Column("scanner_device_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_check_ins_scanner_device_id_scanner_devices",
            "scanner_devices", ["scanner_device_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_check_ins_scanner_device_id", ["scanner_device_id"])


def downgrade() -> None:
    with op.batch_alter_table("check_ins") as batch_op:
        batch_op.drop_index("ix_check_ins_scanner_device_id")
        batch_op.drop_constraint("fk_check_ins_scanner_device_id_scanner_devices", type_="foreignkey")
        batch_op.drop_column("scanner_device_id")
    op.drop_index("ix_scanner_devices_key_id", table_name="scanner_devices")
    op.drop_index("ix_scanner_devices_location_name", table_name="scanner_devices")
    op.drop_index("ix_scanner_devices_id", table_name="scanner_devices")
    op.drop_table("scanner_devices")
