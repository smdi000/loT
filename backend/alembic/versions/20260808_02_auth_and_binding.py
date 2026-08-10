"""Add account credentials and one-owner device binding.

Revision ID: 20260808_02
Revises: 20260808_01
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260808_02"
down_revision = "20260808_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``batch_alter_table`` keeps the migration testable on SQLite while using
    # ordinary ALTER TABLE operations on PostgreSQL.
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("password_hash", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

    with op.batch_alter_table("user_devices") as batch:
        batch.create_unique_constraint("uq_user_devices_device_id", ["device_id"])


def downgrade() -> None:
    with op.batch_alter_table("user_devices") as batch:
        batch.drop_constraint("uq_user_devices_device_id", type_="unique")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("password_hash")
