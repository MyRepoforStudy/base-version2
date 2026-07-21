from __future__ import annotations

ZABBIX_OS_ITEM_KEYS = (
    "system.sw.os.get",
    "system.sw.os",
)

ZABBIX_SERVER_MODEL_ITEM_KEY = "vfs.file.contents[/sys/class/dmi/id/product_name]"
ZABBIX_SERVER_VENDOR_ITEM_KEY = "vfs.file.contents[/sys/class/dmi/id/sys_vendor]"
ZABBIX_CPU_NUM_ITEM_KEY = "system.cpu.num"
ZABBIX_MEM_TOTAL_ITEM_KEY = "vm.memory.size[total]"
ZABBIX_UPTIME_ITEM_KEY = "system.uptime"

ZABBIX_DETAIL_ITEM_KEYS = (
    ZABBIX_CPU_NUM_ITEM_KEY,
    ZABBIX_MEM_TOTAL_ITEM_KEY,
    ZABBIX_UPTIME_ITEM_KEY,
    ZABBIX_SERVER_MODEL_ITEM_KEY,
    ZABBIX_SERVER_VENDOR_ITEM_KEY,
    *ZABBIX_OS_ITEM_KEYS,
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
