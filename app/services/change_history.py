from __future__ import annotations

from datetime import date, datetime

from app.models import HostChange

TRACKED_HOST_FIELDS: dict[str, str] = {
    "hostname": "Hostname",
    "fqdn": "FQDN",
    "ip_address": "IP address",
    "environment": "Environment",
    "datacenter": "Datacenter",
    "proxmox": "Proxmox",
    "system": "System",
    "virtual": "Server type",
    "vendor": "Vendor",
    "model": "Model",
    "os_name": "Operating system",
    "os_support_end_date": "OS support end",
    "cpu_cores": "CPU cores",
    "ram_gb": "RAM",
    "owner": "Owner",
    "department": "Department",
    "business_service": "Business service",
    "criticality": "Criticality",
    "support_end_date": "Hardware support end",
    "notes": "Notes",
    "monitoring_status": "Monitoring status",
}


def serialize_change_value(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "Virtual" if value else "Physical"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def host_change_snapshot(host) -> dict[str, str | None]:
    return {
        field_name: serialize_change_value(getattr(host, field_name, None))
        for field_name in TRACKED_HOST_FIELDS
    }


def record_host_changes(
    db,
    host,
    before: dict[str, str | None],
    source: str,
) -> int:
    after = host_change_snapshot(host)
    change_count = 0
    for field_name in TRACKED_HOST_FIELDS:
        if before.get(field_name) == after.get(field_name):
            continue
        db.add(
            HostChange(
                host_id=host.id,
                field_name=field_name,
                old_value=before.get(field_name),
                new_value=after.get(field_name),
                source=source,
            )
        )
        change_count += 1
    return change_count


def host_change_label(field_name: str) -> str:
    return TRACKED_HOST_FIELDS.get(field_name, field_name.replace("_", " ").title())
