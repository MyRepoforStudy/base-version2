"""add patch compliance, OS lifecycle, and ownership fields

Revision ID: 20260723_0003
Revises: 20260723_0002
Create Date: 2026-07-23 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0003"
down_revision: str | None = "20260723_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hosts", sa.Column("os_family", sa.String(length=60), nullable=True))
    op.add_column("hosts", sa.Column("os_version", sa.String(length=40), nullable=True))
    op.add_column("hosts", sa.Column("os_support_end_date", sa.Date(), nullable=True))
    op.add_column("hosts", sa.Column("os_lifecycle_source", sa.String(length=120), nullable=True))
    op.add_column("hosts", sa.Column("kernel_version", sa.String(length=160), nullable=True))
    op.add_column("hosts", sa.Column("updates_pending", sa.Integer(), nullable=True))
    op.add_column("hosts", sa.Column("security_updates_pending", sa.Integer(), nullable=True))
    op.add_column("hosts", sa.Column("reboot_required", sa.Boolean(), nullable=True))
    op.add_column("hosts", sa.Column("last_patch_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hosts", sa.Column("patch_last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hosts", sa.Column("owner", sa.String(length=160), nullable=True))
    op.add_column("hosts", sa.Column("department", sa.String(length=160), nullable=True))
    op.add_column("hosts", sa.Column("business_service", sa.String(length=160), nullable=True))
    op.add_column(
        "hosts",
        sa.Column("criticality", sa.String(length=20), nullable=False, server_default="UNKNOWN"),
    )
    op.create_index("ix_hosts_os_family", "hosts", ["os_family"])
    op.create_index("ix_hosts_owner", "hosts", ["owner"])
    op.create_index("ix_hosts_department", "hosts", ["department"])
    op.create_index("ix_hosts_business_service", "hosts", ["business_service"])
    op.create_index("ix_hosts_criticality", "hosts", ["criticality"])


def downgrade() -> None:
    op.drop_index("ix_hosts_criticality", table_name="hosts")
    op.drop_index("ix_hosts_business_service", table_name="hosts")
    op.drop_index("ix_hosts_department", table_name="hosts")
    op.drop_index("ix_hosts_owner", table_name="hosts")
    op.drop_index("ix_hosts_os_family", table_name="hosts")
    op.drop_column("hosts", "criticality")
    op.drop_column("hosts", "business_service")
    op.drop_column("hosts", "department")
    op.drop_column("hosts", "owner")
    op.drop_column("hosts", "patch_last_checked_at")
    op.drop_column("hosts", "last_patch_at")
    op.drop_column("hosts", "reboot_required")
    op.drop_column("hosts", "security_updates_pending")
    op.drop_column("hosts", "updates_pending")
    op.drop_column("hosts", "kernel_version")
    op.drop_column("hosts", "os_lifecycle_source")
    op.drop_column("hosts", "os_support_end_date")
    op.drop_column("hosts", "os_version")
    op.drop_column("hosts", "os_family")
