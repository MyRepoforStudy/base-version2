from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Host
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
        },
    )
