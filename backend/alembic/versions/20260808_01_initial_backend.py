"""Initial business backend schema.

Revision ID: 20260808_01
Revises:
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260808_01"
down_revision = None
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devices_product_id", "devices", ["product_id"])
    op.create_table(
        "user_devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "device_id", name="uq_user_devices_user_device"),
    )
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
    op.create_index("ix_user_devices_device_id", "user_devices", ["device_id"])
    op.create_table(
        "tuya_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tuya_msg_id", sa.String(length=255), nullable=True),
        sa.Column("dedup_key", sa.String(length=64), nullable=False),
        sa.Column("biz_code", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_json", json_type, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key", name="uq_tuya_messages_dedup_key"),
        sa.UniqueConstraint("tuya_msg_id", name="uq_tuya_messages_tuya_msg_id"),
    )
    op.create_index("ix_tuya_messages_tuya_msg_id", "tuya_messages", ["tuya_msg_id"])
    op.create_index("ix_tuya_messages_biz_code", "tuya_messages", ["biz_code"])
    op.create_index("ix_tuya_messages_device_id", "tuya_messages", ["device_id"])
    op.create_index("ix_tuya_messages_product_id", "tuya_messages", ["product_id"])
    op.create_table(
        "training_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("external_session_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("total_reps", sa.Integer(), nullable=True),
        sa.Column("avg_confidence", sa.Integer(), nullable=True),
        sa.Column("max_elbow_angle", sa.Integer(), nullable=True),
        sa.Column("max_shoulder_angle", sa.Integer(), nullable=True),
        sa.Column("summary_json", json_type, nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("tuya_msg_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "external_session_id", name="uq_training_sessions_device_external"),
        sa.UniqueConstraint("tuya_msg_id", name="uq_training_sessions_tuya_msg_id"),
    )
    op.create_index("ix_training_sessions_device_id", "training_sessions", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_training_sessions_device_id", table_name="training_sessions")
    op.drop_table("training_sessions")
    op.drop_index("ix_tuya_messages_product_id", table_name="tuya_messages")
    op.drop_index("ix_tuya_messages_device_id", table_name="tuya_messages")
    op.drop_index("ix_tuya_messages_biz_code", table_name="tuya_messages")
    op.drop_index("ix_tuya_messages_tuya_msg_id", table_name="tuya_messages")
    op.drop_table("tuya_messages")
    op.drop_index("ix_user_devices_device_id", table_name="user_devices")
    op.drop_index("ix_user_devices_user_id", table_name="user_devices")
    op.drop_table("user_devices")
    op.drop_index("ix_devices_product_id", table_name="devices")
    op.drop_table("devices")
    op.drop_table("users")
