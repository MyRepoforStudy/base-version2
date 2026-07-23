from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Host, HostFilesystem
from app.services.zabbix import ZabbixApiError, ZabbixClient
from app.services.zabbix_history import backfill_zabbix_metric_history
from app.services.zabbix_items import (
    ZABBIX_AVAILABILITY_ITEM_KEYS,
    ZABBIX_DETAIL_ITEM_KEYS,
    ZABBIX_FILESYSTEM_ITEM_PREFIXES,
    cpu_cores_from_items,
    filesystem_inventory_from_items,
    is_virtual_platform,
    operating_system_item_label,
    patch_inventory_from_items,
    performance_inventory_from_items,
    ram_gb_from_items,
    server_model_item_label,
    server_vendor_item_label,
    uptime_seconds_from_items,
)
from app.services.change_history import host_change_snapshot, record_host_changes
from app.services.compliance import normalize_criticality, parse_date_value, resolve_os_lifecycle
from app.services.metric_history import (
    latest_metric_snapshots,
    prune_metric_history,
    record_metric_snapshot,
)

ENVIRONMENT_TAG_NAMES = ("environment", "env")
DATACENTER_TAG_NAMES = ("datacenter", "data_center", "dc")
PROXMOX_TAG_NAMES = ("proxmox",)
SYSTEM_TAG_NAMES = ("system",)
OWNER_TAG_NAMES = ("owner", "technical_owner", "service_owner")
DEPARTMENT_TAG_NAMES = ("department", "business_unit", "team")
BUSINESS_SERVICE_TAG_NAMES = ("service", "business_service", "application")
CRITICALITY_TAG_NAMES = ("criticality", "importance", "tier")
OS_SUPPORT_END_TAG_NAMES = ("os_support_end", "os_eol", "os_eos")


def normalize_tags(raw_tags: list[dict]) -> dict[str, list[str]]:
    tags: dict[str, set[str]] = {}
    for raw_tag in raw_tags or []:
        tag_name = (raw_tag.get("tag") or "").strip().lower()
        tag_value = (raw_tag.get("value") or "").strip()
        if tag_name and tag_value:
            tags.setdefault(tag_name, set()).add(tag_value)
    return {tag_name: sorted(values) for tag_name, values in sorted(tags.items())}


def first_tag_value(tags: dict[str, list[str]], tag_names: tuple[str, ...]) -> str | None:
    for tag_name in tag_names:
        values = tags.get(tag_name)
        if values:
            return values[0]
    return None


def environment_from_tags(tags: dict[str, list[str]]) -> str:
    value = first_tag_value(tags, ENVIRONMENT_TAG_NAMES)
    if not value:
        return "UNKNOWN"
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"prod", "production"}:
        return "PROD"
    if normalized in {"test", "tst"}:
        return "TEST"
    if normalized in {"dev", "development"}:
        return "DEV"
    if normalized in {"standby", "dr"}:
        return "STANDBY"
    return normalized[:40].upper()


def datacenter_from_tags(tags: dict[str, list[str]]) -> str:
    value = first_tag_value(tags, DATACENTER_TAG_NAMES)
    if not value:
        return "Unknown"
    normalized = value.strip().upper()
    return normalized if normalized in {"MAIN", "DR"} else value.strip()


def normalize_inventory(raw_inventory) -> dict:
    if isinstance(raw_inventory, dict):
        return {key: value for key, value in raw_inventory.items() if value}
    return {}


def sync_host_filesystems(
    db,
    host: Host,
    filesystem_inventory: list[dict[str, float | str | None]],
    observed_at: datetime,
) -> None:
    existing_filesystems = {
        filesystem.mount_point: filesystem
        for filesystem in db.scalars(
            select(HostFilesystem).where(HostFilesystem.host_id == host.id)
        ).all()
    }
    seen_mount_points: set[str] = set()
    for metric in filesystem_inventory:
        mount_point = str(metric["mount_point"])
        seen_mount_points.add(mount_point)
        filesystem = existing_filesystems.get(mount_point)
        if filesystem is None:
            filesystem = HostFilesystem(host_id=host.id, mount_point=mount_point)
            db.add(filesystem)
        filesystem.total_gb = metric["total_gb"]
        filesystem.used_gb = metric["used_gb"]
        filesystem.used_pct = metric["used_pct"]
        filesystem.collected_at = observed_at
    for mount_point, filesystem in existing_filesystems.items():
        if mount_point not in seen_mount_points:
            db.delete(filesystem)


def upsert_host(
    db,
    zabbix_host: dict,
    item_values: dict[str, str],
    problems: list[dict],
    client: ZabbixClient,
) -> tuple[Host, bool]:
    hostid = str(zabbix_host["hostid"])
    inventory_hostname = zabbix_host.get("host") or zabbix_host.get("name") or f"zabbix-{hostid}"
    display_name = zabbix_host.get("name") or inventory_hostname
    tags = normalize_tags(zabbix_host.get("tags") or [])
    inventory = normalize_inventory(zabbix_host.get("inventory"))

    os_name = operating_system_item_label(item_values, inventory.get("os_full") or inventory.get("os"))
    os_support_end_override = parse_date_value(first_tag_value(tags, OS_SUPPORT_END_TAG_NAMES))
    os_lifecycle = resolve_os_lifecycle(os_name, os_support_end_override)
    patch_inventory = patch_inventory_from_items(item_values)
    performance_inventory = performance_inventory_from_items(item_values)
    filesystem_inventory = filesystem_inventory_from_items(item_values)
    vendor = server_vendor_item_label(item_values, inventory.get("vendor"))
    model = server_model_item_label(item_values, inventory.get("hardware_full") or inventory.get("hardware"))
    problem_count = len(problems)
    availability = client.agent_availability_from_host(zabbix_host)
    monitoring_status = client.monitoring_status_from_host(zabbix_host, availability, problem_count)

    host = db.scalar(select(Host).where(Host.zabbix_hostid == hostid))
    created = False
    if host is None:
        host = db.scalar(select(Host).where(Host.hostname == inventory_hostname))
    if host is None:
        created = True
        host = Host(hostname=inventory_hostname)
        db.add(host)
    before = host_change_snapshot(host) if not created else None
    observed_at = datetime.now(UTC)

    host.hostname = inventory_hostname
    host.fqdn = zabbix_host.get("host")
    host.ip_address = client.primary_interface_address(zabbix_host)
    host.environment = environment_from_tags(tags)
    host.datacenter = datacenter_from_tags(tags)
    host.proxmox = first_tag_value(tags, PROXMOX_TAG_NAMES)
    host.system = first_tag_value(tags, SYSTEM_TAG_NAMES)
    host.os_name = os_name
    host.os_family = os_lifecycle.family
    host.os_version = os_lifecycle.version
    host.os_support_end_date = os_lifecycle.support_end
    host.os_lifecycle_source = os_lifecycle.source
    host.vendor = vendor
    host.model = model
    host.virtual = is_virtual_platform(vendor, model)
    host.cpu_cores = cpu_cores_from_items(item_values)
    host.ram_gb = ram_gb_from_items(item_values)
    host.uptime_seconds = uptime_seconds_from_items(item_values)
    host.cpu_utilization_pct = performance_inventory["cpu_utilization_pct"]
    host.memory_utilization_pct = performance_inventory["memory_utilization_pct"]
    host.load_average_1m = performance_inventory["load_average_1m"]
    host.root_disk_total_gb = performance_inventory["root_disk_total_gb"]
    host.root_disk_used_gb = performance_inventory["root_disk_used_gb"]
    host.root_disk_used_pct = performance_inventory["root_disk_used_pct"]
    fullest_filesystem = max(
        (
            filesystem
            for filesystem in filesystem_inventory
            if filesystem["used_pct"] is not None
        ),
        key=lambda filesystem: float(filesystem["used_pct"]),
        default=None,
    )
    host.disk_max_used_pct = fullest_filesystem["used_pct"] if fullest_filesystem else None
    host.disk_max_mount = str(fullest_filesystem["mount_point"]) if fullest_filesystem else None
    host.metrics_collected_at = (
        observed_at
        if performance_inventory["has_performance_data"] or filesystem_inventory
        else None
    )
    host.kernel_version = patch_inventory["kernel_version"]
    host.updates_pending = patch_inventory["updates_pending"]
    host.security_updates_pending = patch_inventory["security_updates_pending"]
    host.reboot_required = patch_inventory["reboot_required"]
    host.last_patch_at = patch_inventory["last_patch_at"]
    host.patch_last_checked_at = observed_at if patch_inventory["has_patch_data"] else None

    owner = first_tag_value(tags, OWNER_TAG_NAMES)
    department = first_tag_value(tags, DEPARTMENT_TAG_NAMES)
    business_service = first_tag_value(tags, BUSINESS_SERVICE_TAG_NAMES)
    criticality = first_tag_value(tags, CRITICALITY_TAG_NAMES)
    if owner:
        host.owner = owner[:160]
    if department:
        host.department = department[:160]
    if business_service:
        host.business_service = business_service[:160]
    if criticality or created or not host.criticality:
        host.criticality = normalize_criticality(criticality)
    host.zabbix_hostid = hostid
    host.zabbix_host_name = display_name
    host.zabbix_url = client.build_host_url(hostid)
    host.zabbix_agent_availability = availability
    host.problem_count = problem_count
    host.monitoring_status = monitoring_status
    host.zabbix_last_sync_at = observed_at
    if created:
        db.flush()
    sync_host_filesystems(db, host, filesystem_inventory, observed_at)
    if before is not None:
        record_host_changes(db, host, before, source="zabbix")
    return host, created


def prune_stale_zabbix_hosts(db, seen_hostids: set[str], verbose: bool = True) -> int:
    imported_hosts = db.scalars(select(Host).where(Host.zabbix_hostid.is_not(None))).all()
    stale_hosts = [host for host in imported_hosts if str(host.zabbix_hostid) not in seen_hostids]
    for host in stale_hosts:
        if verbose:
            print(f"deleted: {host.hostname} hostid={host.zabbix_hostid} no longer in Zabbix group")
        db.delete(host)
    return len(stale_hosts)


def refresh_zabbix_inventory(group_name: str | None = None, verbose: bool = True) -> tuple[int, int, int]:
    settings = get_settings()
    if not settings.zabbix_url or not settings.zabbix_api_token:
        raise RuntimeError("ZABBIX_URL and ZABBIX_API_TOKEN must be set")

    requested_group = group_name or settings.zabbix_host_group
    client = ZabbixClient(
        settings.zabbix_url,
        settings.zabbix_api_token,
        verify_ssl=settings.zabbix_verify_ssl,
        ca_file=settings.zabbix_ca_file,
    )
    groups = client.get_host_groups_by_names([requested_group])
    if not groups:
        raise RuntimeError(f"Zabbix group not found: {requested_group}")

    groupids = [str(group["groupid"]) for group in groups]
    zabbix_hosts = client.get_hosts_by_groupids(groupids)
    if not zabbix_hosts:
        if verbose:
            print(f"No Zabbix hosts found in group: {requested_group}")
        return 0, 0, 0

    hostids = [str(host["hostid"]) for host in zabbix_hosts]
    items_by_host = client.get_latest_item_values_bulk(hostids, ZABBIX_DETAIL_ITEM_KEYS)
    filesystem_item_metadata_by_host = client.get_items_bulk_by_prefix(
        hostids,
        ZABBIX_FILESYSTEM_ITEM_PREFIXES,
    )
    for hostid, filesystem_items in filesystem_item_metadata_by_host.items():
        latest_values = {
            str(item["key_"]): str(item["lastvalue"])
            for item in filesystem_items
            if item.get("key_") and item.get("lastvalue") not in (None, "")
        }
        items_by_host.setdefault(hostid, {}).update(latest_values)
    availability_items_by_host = client.get_items_bulk(
        hostids,
        ZABBIX_AVAILABILITY_ITEM_KEYS,
    )
    problems_by_host = client.get_current_problems_bulk(hostids)

    db = SessionLocal()
    created = 0
    updated = 0
    deleted = 0
    seen_hostids: set[str] = set()
    synced_hosts: list[Host] = []
    try:
        latest_snapshots = latest_metric_snapshots(db)
        for zabbix_host in zabbix_hosts:
            hostid = str(zabbix_host["hostid"])
            if hostid in seen_hostids:
                continue
            seen_hostids.add(hostid)
            host, was_created = upsert_host(
                db,
                zabbix_host,
                items_by_host.get(hostid, {}),
                problems_by_host.get(hostid, []),
                client,
            )
            snapshot = record_metric_snapshot(
                db,
                host,
                latest_snapshots.get(host.id),
                settings.metric_history_interval_seconds,
            )
            if snapshot is not None:
                latest_snapshots[host.id] = snapshot
            synced_hosts.append(host)
            if was_created:
                created += 1
                action = "created"
            else:
                updated += 1
                action = "updated"
            if verbose:
                print(
                    f"{action}: {host.hostname} hostid={host.zabbix_hostid} "
                    f"status={host.monitoring_status} problems={host.problem_count}"
                )
        try:
            backfilled_hosts, backfilled_rows = backfill_zabbix_metric_history(
                db,
                client,
                synced_hosts,
                filesystem_item_metadata_by_host,
                availability_items_by_host,
                settings.zabbix_history_backfill_days,
            )
            if verbose and backfilled_hosts:
                print(
                    f"Zabbix history backfill: hosts={backfilled_hosts} "
                    f"snapshots={backfilled_rows}"
                )
        except ZabbixApiError as exc:
            if verbose:
                print(f"warning: Zabbix history backfill skipped: {exc}")
        deleted = prune_stale_zabbix_hosts(db, seen_hostids, verbose=verbose)
        prune_metric_history(db, settings.metric_history_retention_days)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return created, updated, deleted
