from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Host(TimestampMixin, Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    fqdn: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(40), index=True, default="UNKNOWN")
    datacenter: Mapped[str] = mapped_column(String(40), index=True, default="Unknown")
    proxmox: Mapped[str | None] = mapped_column(String(120), index=True)
    system: Mapped[str | None] = mapped_column(String(120), index=True)
    virtual: Mapped[bool] = mapped_column(Boolean, default=True)
    vendor: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    os_name: Mapped[str | None] = mapped_column(Text)
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    ram_gb: Mapped[float | None] = mapped_column(Float)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer)

    # Only admin-editable field - not derivable from Zabbix.
    support_end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    zabbix_hostid: Mapped[str | None] = mapped_column(String(80), index=True)
    zabbix_host_name: Mapped[str | None] = mapped_column(String(255))
    zabbix_url: Mapped[str | None] = mapped_column(String(500))
    zabbix_agent_availability: Mapped[str] = mapped_column(String(40), index=True, default="unknown")
    problem_count: Mapped[int] = mapped_column(Integer, default=0)
    zabbix_last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monitoring_status: Mapped[str] = mapped_column(String(40), index=True, default="unknown")
