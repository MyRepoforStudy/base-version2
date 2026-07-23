"""add capacity and SLA metric history

Revision ID: 20260724_0005
Revises: 20260723_0004
Create Date: 2026-07-24 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0005"
down_revision: str | None = "20260723_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "host_metric_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("monitoring_status", sa.String(length=40), nullable=False),
        sa.Column("problem_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disk_mount", sa.String(length=255), nullable=True),
        sa.Column("disk_used_pct", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_host_metric_snapshots_host_id",
        "host_metric_snapshots",
        ["host_id"],
    )
    op.create_index(
        "ix_host_metric_snapshots_observed_at",
        "host_metric_snapshots",
        ["observed_at"],
    )
    op.create_index(
        "ix_host_metric_snapshots_host_time",
        "host_metric_snapshots",
        ["host_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_host_metric_snapshots_host_time",
        table_name="host_metric_snapshots",
    )
    op.drop_index(
        "ix_host_metric_snapshots_observed_at",
        table_name="host_metric_snapshots",
    )
    op.drop_index(
        "ix_host_metric_snapshots_host_id",
        table_name="host_metric_snapshots",
    )
    op.drop_table("host_metric_snapshots")
