from __future__ import annotations

from dataclasses import dataclass

from app.services.compliance import lifecycle_status


@dataclass(frozen=True)
class ServerHealth:
    score: int
    status: str
    reasons: tuple[str, ...]


def utilization_status(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= 90:
        return "critical"
    if value >= 75:
        return "warning"
    return "healthy"


def disk_capacity_status(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= 95:
        return "critical"
    if value >= 80:
        return "warning"
    return "healthy"


def _utilization_penalty(value: float | None, label: str) -> tuple[int, str | None]:
    if value is None:
        return 0, None
    if value >= 95:
        return 20, f"{label} utilization is {value:.0f}%"
    if value >= 90:
        return 15, f"{label} utilization is {value:.0f}%"
    if value >= 85:
        return 10, f"{label} utilization is {value:.0f}%"
    if value >= 75:
        return 5, f"{label} utilization is {value:.0f}%"
    return 0, None


def server_health(host) -> ServerHealth:
    score = 100
    reasons: list[str] = []
    monitoring_status = (getattr(host, "monitoring_status", None) or "unknown").lower()
    monitoring_penalties = {
        "problem": (15, "Monitoring reports a problem"),
        "down": (40, "Server is unavailable"),
        "unavailable": (40, "Zabbix agent is unavailable"),
        "disabled": (25, "Monitoring is disabled"),
        "unknown": (8, "Monitoring state is unknown"),
    }
    monitoring_penalty = monitoring_penalties.get(monitoring_status)
    if monitoring_penalty:
        score -= monitoring_penalty[0]
        reasons.append(monitoring_penalty[1])

    problem_count = max(0, getattr(host, "problem_count", 0) or 0)
    if problem_count:
        score -= min(20, problem_count * 4)
        reasons.append(f"{problem_count} active Zabbix problem(s)")

    for value, label in (
        (getattr(host, "cpu_utilization_pct", None), "CPU"),
        (getattr(host, "memory_utilization_pct", None), "Memory"),
    ):
        penalty, reason = _utilization_penalty(value, label)
        score -= penalty
        if reason:
            reasons.append(reason)

    disk_used_pct = getattr(host, "disk_max_used_pct", None)
    if disk_used_pct is None:
        disk_used_pct = getattr(host, "root_disk_used_pct", None)
    disk_mount = getattr(host, "disk_max_mount", None) or "/"
    if disk_used_pct is not None:
        if disk_used_pct >= 95:
            score -= 30
            reasons.append(f"Filesystem {disk_mount} is {disk_used_pct:.0f}% full")
        elif disk_used_pct >= 90:
            score -= 20
            reasons.append(f"Filesystem {disk_mount} is {disk_used_pct:.0f}% full")
        elif disk_used_pct >= 80:
            score -= 10
            reasons.append(f"Filesystem {disk_mount} is {disk_used_pct:.0f}% full")

    os_lifecycle = lifecycle_status(getattr(host, "os_support_end_date", None))
    if os_lifecycle == "eol":
        score -= 20
        reasons.append("Operating system is EOL")
    elif os_lifecycle == "expiring":
        score -= 8
        reasons.append("Operating system support is expiring")

    score = max(0, min(100, score))
    if score >= 85:
        status = "healthy"
    elif score >= 65:
        status = "warning"
    else:
        status = "critical"
    return ServerHealth(score=score, status=status, reasons=tuple(reasons))
