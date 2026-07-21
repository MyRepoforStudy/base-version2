"""initial hosts schema

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hosts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=120), nullable=False),
        sa.Column("fqdn", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("environment", sa.String(length=40), nullable=False, server_default="UNKNOWN"),
        sa.Column("datacenter", sa.String(length=40), nullable=False, server_default="Unknown"),
        sa.Column("virtual", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("vendor", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("os_name", sa.Text(), nullable=True),
        sa.Column("cpu_cores", sa.Integer(), nullable=True),
        sa.Column("ram_gb", sa.Float(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column("support_end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("zabbix_hostid", sa.String(length=80), nullable=True),
        sa.Column("zabbix_host_name", sa.String(length=255), nullable=True),
        sa.Column("zabbix_url", sa.String(length=500), nullable=True),
        sa.Column("zabbix_agent_availability", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.Column("problem_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("zabbix_last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monitoring_status", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname"),
    )
    op.create_index("ix_hosts_environment", "hosts", ["environment"])
    op.create_index("ix_hosts_datacenter", "hosts", ["datacenter"])
    op.create_index("ix_hosts_zabbix_hostid", "hosts", ["zabbix_hostid"])
    op.create_index("ix_hosts_zabbix_agent_availability", "hosts", ["zabbix_agent_availability"])
    op.create_index("ix_hosts_monitoring_status", "hosts", ["monitoring_status"])


def downgrade() -> None:
    op.drop_table("hosts")
