from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta


@dataclass(frozen=True)
class OsLifecycle:
    family: str
    version: str | None
    support_end: date | None
    source: str | None


# Standard/Premier support baselines. Extended support purchased by an
# organisation can be represented with the os_support_end Zabbix tag.
OS_SUPPORT_CATALOG: dict[tuple[str, str], date] = {
    ("Ubuntu", "16.04"): date(2021, 4, 30),
    ("Ubuntu", "18.04"): date(2023, 5, 31),
    ("Ubuntu", "20.04"): date(2025, 5, 31),
    ("Ubuntu", "22.04"): date(2027, 5, 31),
    ("Ubuntu", "24.04"): date(2029, 5, 31),
    ("Ubuntu", "26.04"): date(2031, 5, 31),
    ("Debian", "10"): date(2024, 6, 30),
    ("Debian", "11"): date(2026, 8, 31),
    ("Debian", "12"): date(2028, 6, 30),
    ("Debian", "13"): date(2030, 6, 30),
    ("RHEL", "7"): date(2024, 6, 30),
    ("RHEL", "8"): date(2029, 5, 31),
    ("RHEL", "9"): date(2032, 5, 31),
    ("RHEL", "10"): date(2035, 5, 31),
    ("OEL", "6"): date(2021, 3, 31),
    ("OEL", "7"): date(2024, 12, 31),
    ("OEL", "8"): date(2029, 7, 31),
    ("OEL", "9"): date(2032, 6, 30),
    ("OEL", "10"): date(2035, 6, 30),
    ("Rocky Linux", "8"): date(2029, 5, 31),
    ("Rocky Linux", "9"): date(2032, 5, 31),
    ("AlmaLinux", "8"): date(2029, 5, 31),
    ("AlmaLinux", "9"): date(2032, 5, 31),
    ("CentOS", "7"): date(2024, 6, 30),
    ("CentOS", "8"): date(2021, 12, 31),
}


def _version_match(pattern: str, value: str) -> str | None:
    match = re.search(pattern, value, flags=re.IGNORECASE)
    return match.group(1) if match else None


def detect_os_family_version(os_name: str | None) -> tuple[str, str | None]:
    value = (os_name or "").strip()
    lowered = value.lower()
    if not value:
        return "Unknown", None
    if "ubuntu" in lowered:
        return "Ubuntu", _version_match(r"ubuntu(?: linux)?(?: release)?\s+(\d{2}\.\d{2})", value)
    if "oracle linux" in lowered or "oracle enterprise linux" in lowered:
        return "OEL", _version_match(r"oracle (?:enterprise )?linux(?: server)?(?: release)?\s+(\d+)", value)
    if "red hat" in lowered or re.search(r"\brhel\b", lowered):
        return "RHEL", _version_match(r"(?:red hat enterprise linux(?: server)?|rhel)(?: release)?\s+(\d+)", value)
    if "rocky" in lowered:
        return "Rocky Linux", _version_match(r"rocky(?: linux)?(?: release)?\s+(\d+)", value)
    if "alma" in lowered:
        return "AlmaLinux", _version_match(r"alma(?:linux)?(?: release)?\s+(\d+)", value)
    if "centos" in lowered:
        return "CentOS", _version_match(r"centos(?: linux| stream)?(?: release)?\s+(\d+)", value)
    if "debian" in lowered:
        return "Debian", _version_match(r"debian(?: gnu/linux)?(?: release)?\s+(\d+)", value)
    if "suse" in lowered or "sles" in lowered:
        return "SUSE", _version_match(r"(?:sles|suse(?: linux enterprise server)?)(?: release)?\s+(\d+)", value)
    if "windows" in lowered:
        return "Windows", None
    if "linux" in lowered:
        return "Linux", None
    return value, None


def resolve_os_lifecycle(os_name: str | None, support_end_override: date | None = None) -> OsLifecycle:
    family, version = detect_os_family_version(os_name)
    if support_end_override is not None:
        return OsLifecycle(family, version, support_end_override, "Zabbix tag override")
    support_end = OS_SUPPORT_CATALOG.get((family, version or ""))
    source = "Built-in vendor lifecycle catalog" if support_end else None
    return OsLifecycle(family, version, support_end, source)


def lifecycle_status(support_end: date | None, today: date | None = None) -> str:
    if support_end is None:
        return "unknown"
    today = today or datetime.now(UTC).date()
    if support_end < today:
        return "eol"
    if (support_end - today).days <= 365:
        return "expiring"
    return "active"


def patch_status(
    updates_pending: int | None,
    security_updates_pending: int | None,
    reboot_required: bool | None,
) -> str:
    if updates_pending is None and security_updates_pending is None and reboot_required is None:
        return "unknown"
    if (updates_pending or 0) > 0 or (security_updates_pending or 0) > 0 or reboot_required is True:
        return "action-required"
    return "compliant"


def last_reboot_at(uptime_seconds: int | None, observed_at: datetime | None) -> datetime | None:
    if uptime_seconds is None or uptime_seconds < 0 or observed_at is None:
        return None
    return observed_at - timedelta(seconds=uptime_seconds)


def normalize_criticality(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("_", "-")
    aliases = {
        "critical": "CRITICAL",
        "crit": "CRITICAL",
        "p1": "CRITICAL",
        "tier-0": "CRITICAL",
        "tier0": "CRITICAL",
        "high": "HIGH",
        "p2": "HIGH",
        "tier-1": "HIGH",
        "tier1": "HIGH",
        "medium": "MEDIUM",
        "med": "MEDIUM",
        "p3": "MEDIUM",
        "tier-2": "MEDIUM",
        "tier2": "MEDIUM",
        "low": "LOW",
        "p4": "LOW",
        "tier-3": "LOW",
        "tier3": "LOW",
    }
    return aliases.get(normalized, "UNKNOWN")


def parse_date_value(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for candidate in (text, text.replace(".", "-")):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    for pattern in ("%d-%m-%Y", "%m-%Y"):
        try:
            parsed = datetime.strptime(text.replace(".", "-"), pattern)
            if pattern == "%m-%Y":
                return date(parsed.year, parsed.month, 1)
            return parsed.date()
        except ValueError:
            continue
    return None


def parse_datetime_value(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        timestamp = float(text)
    except ValueError:
        timestamp = None
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
