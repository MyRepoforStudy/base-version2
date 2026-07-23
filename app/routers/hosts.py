from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Host
from app.routers.common import last_reboot_at_for_host, lifecycle_status_for_host, patch_status_for_host
from app.web import templates

router = APIRouter(prefix="/hosts", tags=["hosts"])


def format_uptime(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    days, remainder = divmod(seconds, 86400)
    hours = remainder // 3600
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h"


@router.get("/{host_id}", response_class=HTMLResponse)
def host_detail(host_id: int, request: Request, db: Session = Depends(get_db)):
    host = db.scalar(select(Host).where(Host.id == host_id))
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")

    return templates.TemplateResponse(
        request,
        "host_detail.html",
        {
            "request": request,
            "active_page": "hosts",
            "host": host,
            "uptime_label": format_uptime(host.uptime_seconds),
            "patch_status": patch_status_for_host(host),
            "last_reboot_at": last_reboot_at_for_host(host),
            "lifecycle_status": lifecycle_status_for_host(host),
        },
    )
