from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Host, HostChange, HostFilesystem
from app.routers.common import (
    format_uptime,
    health_for_host,
    last_reboot_at_for_host,
    lifecycle_status_for_host,
)
from app.services.change_history import host_change_label
from app.services.host_health import disk_capacity_status, utilization_status
from app.web import templates

router = APIRouter(prefix="/hosts", tags=["hosts"])


@router.get("/{host_id}", response_class=HTMLResponse)
def host_detail(host_id: int, request: Request, db: Session = Depends(get_db)):
    host = db.scalar(select(Host).where(Host.id == host_id))
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    changes = db.scalars(
        select(HostChange)
        .where(HostChange.host_id == host.id)
        .order_by(HostChange.changed_at.desc(), HostChange.id.desc())
        .limit(100)
    ).all()
    filesystems = db.scalars(
        select(HostFilesystem)
        .where(HostFilesystem.host_id == host.id)
        .order_by(HostFilesystem.mount_point)
    ).all()

    return templates.TemplateResponse(
        request,
        "host_detail.html",
        {
            "request": request,
            "active_page": "hosts",
            "host": host,
            "uptime_label": format_uptime(host.uptime_seconds),
            "health": health_for_host(host),
            "last_reboot_at": last_reboot_at_for_host(host),
            "lifecycle_status": lifecycle_status_for_host(host),
            "disk_status": disk_capacity_status(host.disk_max_used_pct),
            "disk_capacity_status": disk_capacity_status,
            "cpu_status": utilization_status(host.cpu_utilization_pct),
            "memory_status": utilization_status(host.memory_utilization_pct),
            "changes": changes,
            "filesystems": filesystems,
            "host_change_label": host_change_label,
        },
    )
