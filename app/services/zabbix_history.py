from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import insert, select

from app.models import Host, HostMetricSnapshot
from app.services.zabbix_trends import (
    build_host_backfill_rows,
    select_availability_item,
    select_capacity_item,
)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def backfill_zabbix_metric_history(
    db,
    client,
    hosts: list[Host],
    filesystem_items_by_host: dict[str, list[dict[str, Any]]],
    availability_items_by_host: dict[str, list[dict[str, Any]]],
    backfill_days: int,
    now: datetime | None = None,
) -> tuple[int, int]:
    now = now or datetime.now(UTC)
    candidates = [
        host
        for host in hosts
        if host.metric_history_backfilled_at is None and host.zabbix_hostid
    ]
    if not candidates or backfill_days <= 0:
        return 0, 0

    selected_items: dict[int, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {}
    itemids: set[str] = set()
    for host in candidates:
        zabbix_hostid = str(host.zabbix_hostid)
        capacity_item = select_capacity_item(
            host,
            filesystem_items_by_host.get(zabbix_hostid, []),
        )
        availability_item = select_availability_item(
            availability_items_by_host.get(zabbix_hostid, []),
        )
        selected_items[host.id] = (capacity_item, availability_item)
        for item in (capacity_item, availability_item):
            if item and item.get("itemid"):
                itemids.add(str(item["itemid"]))

    trends = client.get_trends(
        sorted(itemids),
        int((now - timedelta(days=backfill_days)).timestamp()),
        int(now.timestamp()),
    )
    trends_by_item: dict[str, list[dict[str, Any]]] = {}
    for trend in trends:
        itemid = str(trend.get("itemid") or "")
        if itemid:
            trends_by_item.setdefault(itemid, []).append(trend)

    cutoff = now - timedelta(days=backfill_days, hours=1)
    existing_rows = db.execute(
        select(
            HostMetricSnapshot.host_id,
            HostMetricSnapshot.observed_at,
        ).where(
            HostMetricSnapshot.host_id.in_([host.id for host in candidates]),
            HostMetricSnapshot.observed_at >= cutoff,
        )
    ).all()
    existing_keys = {
        (host_id, _aware_utc(observed_at))
        for host_id, observed_at in existing_rows
    }

    rows: list[dict[str, Any]] = []
    for host in candidates:
        capacity_item, availability_item = selected_items[host.id]
        for row in build_host_backfill_rows(
            host,
            capacity_item,
            availability_item,
            trends_by_item,
        ):
            key = (host.id, _aware_utc(row["observed_at"]))
            if key not in existing_keys:
                rows.append(row)
                existing_keys.add(key)
        host.metric_history_backfilled_at = now

    for offset in range(0, len(rows), 5000):
        db.execute(insert(HostMetricSnapshot), rows[offset : offset + 5000])
    return len(candidates), len(rows)
