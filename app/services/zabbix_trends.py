from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Any

FILESYSTEM_KEY_PATTERN = re.compile(
    r"^vfs\.fs(?:\.dependent)?\.size\[(.*),(total|used|pused)\]$"
)
AVAILABILITY_KEY_PRIORITY = {
    "agent.ping": 0,
    "icmpping": 1,
}


def _trend_hour(trend: dict[str, Any]) -> datetime | None:
    try:
        clock = int(trend.get("clock"))
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(clock, UTC).replace(minute=0, second=0, microsecond=0)


def _trend_value(trend: dict[str, Any]) -> float | None:
    try:
        value = float(trend.get("value_avg"))
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def select_capacity_item(
    host,
    items: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    if not host.disk_max_mount:
        return None
    candidates: list[tuple[float, int, dict[str, Any]]] = []
    for item in items:
        key = str(item.get("key_") or "")
        match = FILESYSTEM_KEY_PATTERN.match(key)
        if not match:
            continue
        mount_point, metric_name = match.groups()
        if mount_point != host.disk_max_mount or metric_name != "pused":
            continue
        try:
            last_value = float(item.get("lastvalue"))
        except (TypeError, ValueError):
            last_value = host.disk_max_used_pct or 0.0
        distance = (
            abs(last_value - host.disk_max_used_pct)
            if host.disk_max_used_pct is not None
            else 0.0
        )
        dependent_priority = 1 if key.startswith("vfs.fs.dependent.") else 0
        candidates.append((distance, dependent_priority, item))
    return min(candidates, key=lambda candidate: candidate[:2])[2] if candidates else None


def select_availability_item(
    items: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [
        item
        for item in items
        if str(item.get("key_") or "") in AVAILABILITY_KEY_PRIORITY
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: AVAILABILITY_KEY_PRIORITY[str(item.get("key_"))],
    )


def build_host_backfill_rows(
    host,
    capacity_item: dict[str, Any] | None,
    availability_item: dict[str, Any] | None,
    trends_by_item: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows_by_hour: dict[datetime, dict[str, Any]] = {}
    capacity_itemid = str(capacity_item.get("itemid")) if capacity_item else None
    if capacity_itemid:
        for trend in trends_by_item.get(capacity_itemid, []):
            observed_at = _trend_hour(trend)
            value = _trend_value(trend)
            if observed_at is None or value is None or not 0 <= value <= 100:
                continue
            rows_by_hour[observed_at] = {
                "host_id": host.id,
                "observed_at": observed_at,
                "monitoring_status": "unknown",
                "problem_count": 0,
                "disk_mount": host.disk_max_mount,
                "disk_used_pct": round(value, 3),
            }

    availability_itemid = (
        str(availability_item.get("itemid"))
        if availability_item
        else None
    )
    availability_by_hour: dict[datetime, float] = {}
    if availability_itemid:
        for trend in trends_by_item.get(availability_itemid, []):
            observed_at = _trend_hour(trend)
            value = _trend_value(trend)
            if observed_at is not None and value is not None:
                availability_by_hour[observed_at] = value
    if availability_by_hour:
        observed_at = min(availability_by_hour)
        last_observed_at = max(availability_by_hour)
        while observed_at <= last_observed_at:
            value = availability_by_hour.get(observed_at)
            status = "ok" if value is not None and value > 0 else "down"
            row = rows_by_hour.setdefault(
                observed_at,
                {
                    "host_id": host.id,
                    "observed_at": observed_at,
                    "monitoring_status": status,
                    "problem_count": 0,
                    "disk_mount": None,
                    "disk_used_pct": None,
                },
            )
            row["monitoring_status"] = status
            observed_at += timedelta(hours=1)

    return [rows_by_hour[observed_at] for observed_at in sorted(rows_by_hour)]
