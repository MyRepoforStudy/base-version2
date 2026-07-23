from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HostMetricSnapshot(Base):
    __tablename__ = "host_metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"),
        index=True,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    monitoring_status: Mapped[str] = mapped_column(String(40))
    problem_count: Mapped[int] = mapped_column(Integer, default=0)
    disk_mount: Mapped[str | None] = mapped_column(String(255))
    disk_used_pct: Mapped[float | None] = mapped_column(Float)
