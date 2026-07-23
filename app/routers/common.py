from datetime import UTC, date, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Host


def active_filters(
    environment: str | None = None,
    virtual: str | None = None,
    proxmox: str | None = None,
    system: str | None = None,
    os_family: str | None = None,
    q: str | None = None,
) -> dict[str, str]:
    values = {
        "environment": environment,
        "virtual": virtual,
        "proxmox": proxmox,
        "system": system,
        "os_family": os_family,
        "q": q,
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
    return stmt


def os_family_label(os_name: str | None) -> str:
    normalized = (os_name or "").strip().lower()
    if not normalized:
        return "Unknown"
    if "ubuntu" in normalized:
        return "Ubuntu"
    if "oracle linux" in normalized or "oracle enterprise linux" in normalized:
        return "OEL"
    if "red hat" in normalized or "rhel" in normalized:
        return "RHEL"
    if "rocky" in normalized:
        return "Rocky Linux"
    if "alma" in normalized:
        return "AlmaLinux"
    if "centos" in normalized:
        return "CentOS"
    if "debian" in normalized:
        return "Debian"
    if "suse" in normalized or "sles" in normalized:
        return "SUSE"
    if "windows" in normalized:
        return "Windows"
    if "linux" in normalized:
        return "Linux"
    return os_name.strip()


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
            )
            if value
        ).lower()

    return [host for host in hosts if query in haystack(host)]


def support_status_label(support_end_date: date | None) -> str:
    if support_end_date is None:
        return "not set"
    today = datetime.now(UTC).date()
    if support_end_date < today:
        return "expired"
    if (support_end_date - today).days <= 180:
        return "expires soon"
    return "active"
