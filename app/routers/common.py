from datetime import UTC, date, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Host
from app.services.compliance import (
    detect_os_family_version,
    format_uptime,
    last_reboot_at,
    lifecycle_status,
)


def active_filters(
    environment: str | None = None,
    virtual: str | None = None,
    proxmox: str | None = None,
    system: str | None = None,
    os_family: str | None = None,
    q: str | None = None,
    lifecycle: str | None = None,
) -> dict[str, str]:
    values = {
        "environment": environment,
        "virtual": virtual,
        "proxmox": proxmox,
        "system": system,
        "os_family": os_family,
        "q": q,
        "lifecycle": lifecycle,
    }
    return {key: value for key, value in values.items() if value}


def distinct_values(db: Session, column) -> list[str]:
    values = db.scalars(select(column).where(column.is_not(None), column != "").distinct().order_by(column)).all()
    return [value for value in values if value]


def get_filter_options(db: Session) -> dict[str, list[str]]:
    return {
        "environments": distinct_values(db, Host.environment),
        "proxmox_values": distinct_values(db, Host.proxmox),
        "system_values": distinct_values(db, Host.system),
    }


def normalized_virtual_filter(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    return normalized if normalized in {"YES", "NO"} else None


def apply_host_filters(
    stmt: Select,
    environment: str | None = None,
    virtual: str | None = None,
    proxmox: str | None = None,
    system: str | None = None,
    criticality: str | None = None,
) -> Select:
    if environment:
        stmt = stmt.where(Host.environment == environment.upper())
    active_virtual = normalized_virtual_filter(virtual)
    if active_virtual == "YES":
        stmt = stmt.where(Host.virtual.is_(True))
    elif active_virtual == "NO":
        stmt = stmt.where(Host.virtual.is_(False))
    if proxmox:
        stmt = stmt.where(Host.proxmox == proxmox)
    if system:
        stmt = stmt.where(Host.system == system)
    if criticality:
        stmt = stmt.where(Host.criticality == criticality.upper())
    return stmt


def os_family_label(os_name: str | None) -> str:
    return detect_os_family_version(os_name)[0]


def apply_os_family_filter(hosts: list[Host], os_family: str | None) -> list[Host]:
    if not os_family:
        return hosts
    return [host for host in hosts if os_family_label(host.os_name) == os_family]


def apply_search_filter(hosts: list[Host], q: str | None) -> list[Host]:
    query = (q or "").strip().lower()
    if not query:
        return hosts

    def haystack(host: Host) -> str:
        return " ".join(
            str(value)
            for value in (
                host.hostname,
                host.zabbix_host_name,
                host.ip_address,
                host.vendor,
                host.model,
                host.os_name,
                host.system,
                host.proxmox,
                host.environment,
                host.datacenter,
                host.kernel_version,
                host.owner,
                host.department,
                host.business_service,
                host.criticality,
            )
            if value
        ).lower()

    return [host for host in hosts if query in haystack(host)]


def last_reboot_at_for_host(host: Host) -> datetime | None:
    return last_reboot_at(host.uptime_seconds, host.zabbix_last_sync_at)


def lifecycle_status_for_host(host: Host) -> str:
    return lifecycle_status(host.os_support_end_date)


def apply_operational_filters(
    hosts: list[Host],
    lifecycle: str | None = None,
) -> list[Host]:
    selected = hosts
    if lifecycle:
        selected = [host for host in selected if lifecycle_status_for_host(host) == lifecycle]
    return selected


SORT_COLUMNS: dict[str, object] = {
    "hostname": lambda host: (host.zabbix_host_name or host.hostname or "").lower(),
    "ip_address": lambda host: host.ip_address or "",
    "environment": lambda host: host.environment or "",
    "system": lambda host: (host.system or "").lower(),
    "proxmox": lambda host: (host.proxmox or "").lower(),
    "virtual": lambda host: host.virtual,
    "vendor": lambda host: (host.vendor or "").lower(),
    "model": lambda host: (host.model or "").lower(),
    "cpu_cores": lambda host: host.cpu_cores if host.cpu_cores is not None else -1,
    "ram_gb": lambda host: host.ram_gb if host.ram_gb is not None else -1,
    "uptime_seconds": lambda host: host.uptime_seconds if host.uptime_seconds is not None else -1,
    "os_name": lambda host: (host.os_name or "").lower(),
    "monitoring_status": lambda host: host.monitoring_status or "",
    "os_lifecycle": lambda host: (
        host.os_support_end_date.toordinal() if host.os_support_end_date is not None else -1
    ),
    "owner": lambda host: (host.owner or "").lower(),
    "criticality": lambda host: {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
        "UNKNOWN": 0,
    }.get(host.criticality or "UNKNOWN", 0),
}


def sort_hosts(hosts: list[Host], sort: str | None, sort_dir: str | None) -> list[Host]:
    key = SORT_COLUMNS.get(sort or "")
    if key is None:
        return hosts
    return sorted(hosts, key=key, reverse=(sort_dir == "desc"))


def support_status_label(support_end_date: date | None) -> str:
    if support_end_date is None:
        return "not set"
    today = datetime.now(UTC).date()
    if support_end_date < today:
        return "expired"
    if (support_end_date - today).days <= 180:
        return "expires soon"
    return "active"
