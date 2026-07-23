from io import BytesIO
from typing import Iterable

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Host
from app.routers.common import (
    apply_host_filters,
    apply_operational_filters,
    format_uptime,
    last_reboot_at_for_host,
    lifecycle_status_for_host,
)
from app.services.zabbix_refresh import maybe_refresh_zabbix_cache

router = APIRouter(prefix="/exports", tags=["exports"])


def apply_sheet_style(ws, headers: Iterable[str]) -> None:
    header_fill = PatternFill("solid", fgColor="E9EEF5")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for index, header in enumerate(headers, start=1):
        ws.column_dimensions[ws.cell(row=1, column=index).column_letter].width = max(14, len(header) + 2)


@router.get("/hosts.xlsx")
def export_hosts(
    environment: str | None = None,
    virtual: str | None = None,
    proxmox: str | None = None,
    system: str | None = None,
    criticality: str | None = None,
    lifecycle: str | None = None,
    db: Session = Depends(get_db),
):
    maybe_refresh_zabbix_cache(db)
    stmt = select(Host).order_by(Host.hostname)
    stmt = apply_host_filters(stmt, environment, virtual, proxmox, system, criticality)
    hosts = db.scalars(stmt).all()
    hosts = apply_operational_filters(hosts, lifecycle=lifecycle)

    headers = [
        "hostname",
        "ip_address",
        "environment",
        "datacenter",
        "virtual",
        "vendor",
        "model",
        "cpu_cores",
        "ram_gb",
        "uptime_seconds",
        "uptime",
        "last_reboot_at",
        "os_name",
        "os_family",
        "os_version",
        "os_support_end_date",
        "os_lifecycle_status",
        "owner",
        "department",
        "business_service",
        "criticality",
        "monitoring_status",
        "problem_count",
        "support_end_date",
        "zabbix_hostid",
        "zabbix_host_name",
        "zabbix_last_sync_at",
    ]
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Servers"
    ws.append(headers)
    for host in hosts:
        last_reboot = last_reboot_at_for_host(host)
        ws.append(
            [
                host.hostname,
                host.ip_address,
                host.environment,
                host.datacenter,
                "Virtual" if host.virtual else "Physical",
                host.vendor,
                host.model,
                host.cpu_cores,
                host.ram_gb,
                host.uptime_seconds,
                format_uptime(host.uptime_seconds),
                last_reboot.replace(tzinfo=None) if last_reboot else None,
                host.os_name,
                host.os_family,
                host.os_version,
                host.os_support_end_date,
                lifecycle_status_for_host(host),
                host.owner,
                host.department,
                host.business_service,
                host.criticality,
                host.monitoring_status,
                host.problem_count,
                host.support_end_date,
                host.zabbix_hostid,
                host.zabbix_host_name,
                host.zabbix_last_sync_at.replace(tzinfo=None) if host.zabbix_last_sync_at else None,
            ]
        )
    apply_sheet_style(ws, headers)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="server_inventory_hosts.xlsx"'},
    )
