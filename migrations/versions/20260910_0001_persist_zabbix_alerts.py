"""Persist Zabbix incidents, alert events and notification attempts.

Revision ID: 20260910_0001
Revises:
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_event_id", sa.String(length=255), nullable=False),
        sa.Column("service", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("severity", sa.String(length=64), nullable=False),
        sa.Column("current_status", sa.String(length=64), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "source_event_id",
            name="uq_incidents_source_event",
        ),
    )
    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_event_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "source_event_id",
            "status",
            name="uq_alert_events_transition",
        ),
    )
    op.create_index(
        "ix_alert_events_incident_id",
        "alert_events",
        ["incident_id"],
    )
    op.create_table(
        "notification_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_event_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["alert_event_id"],
            ["alert_events.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_attempts_alert_event_id",
        "notification_attempts",
        ["alert_event_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_attempts_alert_event_id",
        table_name="notification_attempts",
    )
    op.drop_table("notification_attempts")
    op.drop_index("ix_alert_events_incident_id", table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_table("incidents")
