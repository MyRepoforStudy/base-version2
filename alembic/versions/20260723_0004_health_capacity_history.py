"""add health metrics and host change history

Revision ID: 20260723_0004
Revises: 20260723_0003
Create Date: 2026-07-23 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0004"
down_revision: str | None = "20260723_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hosts", sa.Column("cpu_utilization_pct", sa.Float(), nullable=True))
    op.add_column("hosts", sa.Column("memory_utilization_pct", sa.Float(), nullable=True))
    op.add_column("hosts", sa.Column("load_average_1m", sa.Float(), nullable=True))
    op.add_column("hosts", sa.Column("root_disk_total_gb", sa.Float(), nullable=True))
    op.add_column("hosts", sa.Column("root_disk_used_gb", sa.Float(), nullable=True))
    op.add_column("hosts", sa.Column("root_disk_used_pct", sa.Float(), nullable=True))
    op.add_column("hosts", sa.Column("disk_max_used_pct", sa.Float(), nullable=True))
    op.add_column("hosts", sa.Column("disk_max_mount", sa.String(length=255), nullable=True))
    op.add_column("hosts", sa.Column("metrics_collected_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "host_filesystems",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("mount_point", sa.String(length=255), nullable=False),
        sa.Column("total_gb", sa.Float(), nullable=True),
        sa.Column("used_gb", sa.Float(), nullable=True),
        sa.Column("used_pct", sa.Float(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("host_id", "mount_point"),
    )
    op.create_index("ix_host_filesystems_host_id", "host_filesystems", ["host_id"])

    op.create_table(
        "host_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="zabbix"),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_host_changes_host_id", "host_changes", ["host_id"])
    op.create_index("ix_host_changes_changed_at", "host_changes", ["changed_at"])
    op.create_index(
        "ix_host_changes_host_id_changed_at",
        "host_changes",
        ["host_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_host_changes_host_id_changed_at", table_name="host_changes")
    op.drop_index("ix_host_changes_changed_at", table_name="host_changes")
    op.drop_index("ix_host_changes_host_id", table_name="host_changes")
    op.drop_table("host_changes")
    op.drop_index("ix_host_filesystems_host_id", table_name="host_filesystems")
    op.drop_table("host_filesystems")
    op.drop_column("hosts", "metrics_collected_at")
    op.drop_column("hosts", "disk_max_mount")
    op.drop_column("hosts", "disk_max_used_pct")
    op.drop_column("hosts", "root_disk_used_pct")
    op.drop_column("hosts", "root_disk_used_gb")
    op.drop_column("hosts", "root_disk_total_gb")
    op.drop_column("hosts", "load_average_1m")
    op.drop_column("hosts", "memory_utilization_pct")
    op.drop_column("hosts", "cpu_utilization_pct")
