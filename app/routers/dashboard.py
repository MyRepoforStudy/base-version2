from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import get_settings
from app.models import Host, HostMetricSnapshot
from app.routers.common import (
    active_filters,
    apply_host_filters,
    apply_operational_filters,
    apply_os_family_filter,
    apply_search_filter,
    format_uptime,
    get_filter_options,
    health_for_host,
    last_reboot_at_for_host,
    lifecycle_status_for_host,
    normalized_virtual_filter,
    os_family_label,
    sort_hosts,
    support_status_label,
)
from app.services.host_health import disk_capacity_status, utilization_status
from app.services.capacity_sla import availability_sla, capacity_forecast
from app.services.zabbix_refresh import maybe_refresh_zabbix_cache
from app.web import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    view: str = "overview",
    environment: str | None = None,
    virtual: str | None = None,
    proxmox: str | None = None,
    system: str | None = None,
    os_family: str | None = None,
    q: str | None = None,
    lifecycle: str | None = None,
    health: str | None = None,
    sort: str | None = None,
    dir: str = "asc",
    refresh: bool = False,
    db: Session = Depends(get_db),
):
    current_view = (
        view
        if view in {"overview", "hosts", "performance", "capacity"}
        else "overview"
    )
    if current_view == "hosts" and sort in {
        "cpu_utilization_pct",
        "memory_utilization_pct",
        "disk_max_used_pct",
        "uptime_seconds",
    }:
        current_view = "performance"
    active_health = health if current_view == "performance" else None
    filters = active_filters(
        environment=environment,
        virtual=virtual,
        proxmox=proxmox,
        system=system,
        os_family=os_family,
        q=q,
        lifecycle=lifecycle,
        health=active_health,
    )
    zabbix_refresh_error = maybe_refresh_zabbix_cache(db, force=refresh)

    all_hosts = db.scalars(select(Host).order_by(Host.hostname)).all()
    total = len(all_hosts)

    virtual_count = sum(1 for host in all_hosts if host.virtual)
    physical_count = total - virtual_count

    environment_counter = Counter((host.environment or "UNKNOWN") for host in all_hosts)
    environment_counts = sorted(environment_counter.items())

    datacenter_counter = Counter((host.datacenter or "Unknown") for host in all_hosts)
    datacenter_counts = {
        "MAIN": datacenter_counter.get("MAIN", 0),
        "DR": datacenter_counter.get("DR", 0),
    }

    os_counter = Counter(os_family_label(host.os_name) for host in all_hosts)
    os_counts = sorted(os_counter.items(), key=lambda item: (-item[1], item[0]))

    monitoring_counter = Counter((host.monitoring_status or "unknown") for host in all_hosts)
    monitoring_counts = sorted(monitoring_counter.items())
    physical_server_rows = [
        {
            "host": host,
            "model": host.model or "-",
            "vendor": host.vendor or "-",
            "datacenter": host.datacenter or "Unknown",
            "support_status": support_status_label(host.support_end_date),
        }
        for host in all_hosts
        if not host.virtual
    ]
    physical_server_rows.sort(key=lambda row: (row["vendor"], row["model"], row["host"].hostname))

    last_sync_at = db.scalar(select(func.max(Host.zabbix_last_sync_at)))
    zabbix_inventory_warning = None
    if total == 0:
        zabbix_inventory_warning = "No cached Zabbix hosts yet. Click Refresh Zabbix to load live data."

    hosts_stmt = select(Host).order_by(Host.hostname)
    hosts_stmt = apply_host_filters(hosts_stmt, environment, virtual, proxmox, system)
    filtered_hosts = db.scalars(hosts_stmt).all()
    filtered_hosts = apply_os_family_filter(filtered_hosts, os_family)
    filtered_hosts = apply_search_filter(filtered_hosts, q)
    filtered_hosts = apply_operational_filters(
        filtered_hosts,
        lifecycle=lifecycle,
        health=active_health,
    )
    sort_dir = "desc" if dir == "desc" else "asc"
    filtered_hosts = sort_hosts(filtered_hosts, sort, sort_dir)

    capacity_rows = []
    capacity_at_risk_count = 0
    sla_missed_count = 0
    history_collecting_count = 0
    settings = get_settings()
    if current_view == "capacity" and filtered_hosts:
        now = datetime.now(UTC)
        snapshot_cutoff = now - timedelta(days=30, hours=2)
        host_ids = [host.id for host in filtered_hosts]
        snapshots = db.scalars(
            select(HostMetricSnapshot)
            .where(
                HostMetricSnapshot.host_id.in_(host_ids),
                HostMetricSnapshot.observed_at >= snapshot_cutoff,
            )
            .order_by(
                HostMetricSnapshot.host_id,
                HostMetricSnapshot.observed_at,
            )
        ).all()
        snapshots_by_host: dict[int, list[HostMetricSnapshot]] = {
            host_id: [] for host_id in host_ids
        }
        for snapshot in snapshots:
            snapshots_by_host.setdefault(snapshot.host_id, []).append(snapshot)
        for host in filtered_hosts:
            host_snapshots = snapshots_by_host.get(host.id, [])
            forecast = capacity_forecast(
                host_snapshots,
                current_pct=host.disk_max_used_pct,
                mount_point=host.disk_max_mount,
                target_pct=settings.capacity_forecast_target_percent,
                now=now,
            )
            sla = availability_sla(
                host_snapshots,
                target_percent=settings.sla_target_percent,
                window_days=30,
                max_gap_seconds=max(
                    settings.metric_history_interval_seconds * 2,
                    7200,
                ),
                now=now,
            )
            capacity_rows.append(
                {
                    "host": host,
                    "forecast": forecast,
                    "sla": sla,
                }
            )
            if forecast.status in {"critical", "warning"}:
                capacity_at_risk_count += 1
            if sla.status == "missed":
                sla_missed_count += 1
            if forecast.status == "collecting" or sla.status == "collecting":
                history_collecting_count += 1

    os_family_options = sorted({os_family_label(host.os_name) for host in all_hosts})

    chart_data = {
        "platformLabels": ["Virtual", "Physical"],
        "platformValues": [virtual_count, physical_count],
        "osLabels": [label for label, _ in os_counts],
        "osValues": [count for _, count in os_counts],
        "environmentLabels": [label for label, _ in environment_counts],
        "environmentValues": [count for _, count in environment_counts],
        "monitoringLabels": [label for label, _ in monitoring_counts],
        "monitoringValues": [count for _, count in monitoring_counts],
    }

    filter_options = get_filter_options(db)
    filter_options["os_families"] = os_family_options

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "active_page": "dashboard" if current_view == "overview" else "hosts",
            "current_view": current_view,
            "total": total,
            "virtual_count": virtual_count,
            "physical_count": physical_count,
            "environment_counts": environment_counts,
            "datacenter_counts": datacenter_counts,
            "os_counts": os_counts,
            "monitoring_counts": monitoring_counts,
            "physical_server_rows": physical_server_rows,
            "last_sync_at": last_sync_at,
            "zabbix_refresh_error": zabbix_refresh_error,
            "zabbix_inventory_warning": zabbix_inventory_warning,
            "hosts": filtered_hosts,
            "capacity_rows": capacity_rows,
            "capacity_at_risk_count": capacity_at_risk_count,
            "sla_missed_count": sla_missed_count,
            "history_collecting_count": history_collecting_count,
            "sla_target_percent": settings.sla_target_percent,
            "capacity_forecast_target_percent": settings.capacity_forecast_target_percent,
            "filters": filters,
            "filter_options": filter_options,
            "active_virtual_filter": normalized_virtual_filter(virtual),
            "sort": sort,
            "sort_dir": sort_dir,
            "chart_data": chart_data,
            "format_uptime": format_uptime,
            "health_for_host": health_for_host,
            "disk_capacity_status": disk_capacity_status,
            "utilization_status": utilization_status,
            "last_reboot_at_for_host": last_reboot_at_for_host,
            "lifecycle_status_for_host": lifecycle_status_for_host,
        },
    )
