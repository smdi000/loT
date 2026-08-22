"""Add the nullable canonical training type to training sessions.

Revision ID: 20260822_03
Revises: 20260808_02
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260822_03"
down_revision = "20260808_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.add_column(sa.Column("training_type", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.drop_column("training_type")
