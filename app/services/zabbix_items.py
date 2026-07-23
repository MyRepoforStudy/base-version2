from __future__ import annotations

import json
import re

from app.services.compliance import parse_datetime_value

ZABBIX_OS_ITEM_KEYS = (
    "system.sw.os.get",
    "system.sw.os",
)

ZABBIX_SERVER_MODEL_ITEM_KEY = "vfs.file.contents[/sys/class/dmi/id/product_name]"
ZABBIX_SERVER_VENDOR_ITEM_KEY = "vfs.file.contents[/sys/class/dmi/id/sys_vendor]"
ZABBIX_CPU_NUM_ITEM_KEY = "system.cpu.num"
ZABBIX_MEM_TOTAL_ITEM_KEY = "vm.memory.size[total]"
ZABBIX_UPTIME_ITEM_KEY = "system.uptime"
ZABBIX_KERNEL_ITEM_KEYS = (
    "system.kernel.version",
    "kernel.version",
    "system.uname",
)
ZABBIX_UPDATES_PENDING_ITEM_KEYS = (
    "linux.updates.pending",
    "system.updates.pending",
    "system.sw.updates.count",
    "package.updates.pending",
    "apt.updates.pending",
    "dnf.updates.pending",
)
ZABBIX_SECURITY_UPDATES_ITEM_KEYS = (
    "linux.updates.security",
    "system.updates.security",
    "system.sw.updates.security",
    "package.updates.security",
    "apt.updates.security",
    "dnf.updates.security",
)
ZABBIX_REBOOT_REQUIRED_ITEM_KEYS = (
    "linux.reboot.required",
    "system.reboot.required",
    "reboot.required",
)
ZABBIX_LAST_PATCH_ITEM_KEYS = (
    "linux.patch.last",
    "system.patch.last",
    "patch.last.success",
)

ZABBIX_PATCH_ITEM_KEYS = (
    *ZABBIX_KERNEL_ITEM_KEYS,
    *ZABBIX_UPDATES_PENDING_ITEM_KEYS,
    *ZABBIX_SECURITY_UPDATES_ITEM_KEYS,
    *ZABBIX_REBOOT_REQUIRED_ITEM_KEYS,
    *ZABBIX_LAST_PATCH_ITEM_KEYS,
)

ZABBIX_DETAIL_ITEM_KEYS = (
    ZABBIX_CPU_NUM_ITEM_KEY,
    ZABBIX_MEM_TOTAL_ITEM_KEY,
    ZABBIX_UPTIME_ITEM_KEY,
    ZABBIX_SERVER_MODEL_ITEM_KEY,
    ZABBIX_SERVER_VENDOR_ITEM_KEY,
    *ZABBIX_OS_ITEM_KEYS,
    *ZABBIX_PATCH_ITEM_KEYS,
)


def clean_item_text(value: str | None, max_length: int | None = None) -> str | None:
    if not value:
        return None
    text = " ".join(value.split())
    if not text or text.lower() in {"none", "unknown", "not specified", "to be filled by o.e.m."}:
        return None
    if max_length and len(text) > max_length:
        return f"{text[: max_length - 3].rstrip()}..."
    return text


def operating_system_item_label(item_values: dict[str, str], fallback: str | None = None) -> str | None:
    for key in ZABBIX_OS_ITEM_KEYS:
        value = item_values.get(key)
        if value:
            if key == "system.sw.os.get":
                try:
                    payload = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    payload = None
                if isinstance(payload, dict):
                    version_full = (
                        payload.get("version_full")
                        or payload.get("PRETTY_NAME")
                        or payload.get("pretty_name")
                    )
                    if version_full:
                        return clean_item_text(str(version_full), max_length=80)
                    product = payload.get("product_name") or payload.get("NAME") or payload.get("name")
                    version = payload.get("version") or payload.get("VERSION_ID") or payload.get("version_id")
                    combined = " ".join(str(part) for part in (product, version) if part)
                    if combined:
                        return clean_item_text(combined, max_length=80)
            return clean_item_text(value, max_length=80)
    return clean_item_text(fallback, max_length=80)


def server_model_item_label(item_values: dict[str, str], fallback: str | None = None) -> str | None:
    return clean_item_text(item_values.get(ZABBIX_SERVER_MODEL_ITEM_KEY)) or clean_item_text(fallback)


def server_vendor_item_label(item_values: dict[str, str], fallback: str | None = None) -> str | None:
    return clean_item_text(item_values.get(ZABBIX_SERVER_VENDOR_ITEM_KEY)) or clean_item_text(fallback)


def cpu_cores_from_items(item_values: dict[str, str]) -> int | None:
    value = item_values.get(ZABBIX_CPU_NUM_ITEM_KEY)
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def ram_gb_from_items(item_values: dict[str, str]) -> float | None:
    value = item_values.get(ZABBIX_MEM_TOTAL_ITEM_KEY)
    if not value:
        return None
    try:
        return round(float(value) / 1024**3, 1)
    except ValueError:
        return None


def uptime_seconds_from_items(item_values: dict[str, str]) -> int | None:
    value = item_values.get(ZABBIX_UPTIME_ITEM_KEY)
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def first_item_value(item_values: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item_values.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def integer_from_items(item_values: dict[str, str], keys: tuple[str, ...]) -> int | None:
    value = first_item_value(item_values, keys)
    if value is None:
        return None
    try:
        return max(0, int(float(value.strip())))
    except ValueError:
        return None


def boolean_from_items(item_values: dict[str, str], keys: tuple[str, ...]) -> bool | None:
    value = first_item_value(item_values, keys)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "required", "pending", "reboot required"}:
        return True
    if normalized in {"0", "false", "no", "not required", "none", "ok"}:
        return False
    return None


def kernel_version_from_items(item_values: dict[str, str]) -> str | None:
    value = clean_item_text(first_item_value(item_values, ZABBIX_KERNEL_ITEM_KEYS), max_length=160)
    if not value:
        return None
    match = re.search(r"\b(\d+\.\d+(?:\.\d+)?[^\s]*)", value)
    return match.group(1) if match else value


def patch_inventory_from_items(item_values: dict[str, str]) -> dict[str, object]:
    return {
        "kernel_version": kernel_version_from_items(item_values),
        "updates_pending": integer_from_items(item_values, ZABBIX_UPDATES_PENDING_ITEM_KEYS),
        "security_updates_pending": integer_from_items(item_values, ZABBIX_SECURITY_UPDATES_ITEM_KEYS),
        "reboot_required": boolean_from_items(item_values, ZABBIX_REBOOT_REQUIRED_ITEM_KEYS),
        "last_patch_at": parse_datetime_value(first_item_value(item_values, ZABBIX_LAST_PATCH_ITEM_KEYS)),
        "has_patch_data": any(key in item_values for key in ZABBIX_PATCH_ITEM_KEYS),
    }


VIRTUAL_PLATFORM_MARKERS = (
    "qemu",
    "kvm",
    "vmware",
    "virtualbox",
    "virtual machine",
    "hyper-v",
    "hyperv",
    "proxmox",
    "xen",
    "bochs",
    "virtual",
    "parallels",
    "openstack",
    "cloud",
    "rhev",
    "ovirt",
)

PHYSICAL_PLATFORM_MARKERS = (
    "dell",
    "hpe",
    "hewlett packard",
    "hewlett-packard",
    "lenovo",
    "ibm",
    "cisco",
    "supermicro",
    "super micro",
    "fujitsu",
    "oracle corporation",
    "huawei",
    "inspur",
    "bare metal",
    "baremetal",
)


def is_virtual_platform(vendor: str | None, model: str | None) -> bool:
    text = " ".join(value for value in (vendor, model) if value).lower()
    if not text:
        return True
    if any(marker in text for marker in VIRTUAL_PLATFORM_MARKERS):
        return True
    if any(marker in text for marker in PHYSICAL_PLATFORM_MARKERS):
        return False
    return True
