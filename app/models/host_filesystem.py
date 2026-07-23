from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HostFilesystem(Base):
    __tablename__ = "host_filesystems"
    __table_args__ = (UniqueConstraint("host_id", "mount_point"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"),
        index=True,
    )
    mount_point: Mapped[str] = mapped_column(String(255))
    total_gb: Mapped[float | None] = mapped_column(Float)
    used_gb: Mapped[float | None] = mapped_column(Float)
    used_pct: Mapped[float | None] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
