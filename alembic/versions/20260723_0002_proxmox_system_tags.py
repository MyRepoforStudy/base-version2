"""add proxmox and system tag columns

Revision ID: 20260723_0002
Revises: 20260721_0001
Create Date: 2026-07-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0002"
down_revision: str | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hosts", sa.Column("proxmox", sa.String(length=120), nullable=True))
    op.add_column("hosts", sa.Column("system", sa.String(length=120), nullable=True))
    op.create_index("ix_hosts_proxmox", "hosts", ["proxmox"])
    op.create_index("ix_hosts_system", "hosts", ["system"])


def downgrade() -> None:
    op.drop_index("ix_hosts_system", table_name="hosts")
    op.drop_index("ix_hosts_proxmox", table_name="hosts")
    op.drop_column("hosts", "system")
    op.drop_column("hosts", "proxmox")
