from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, select

from app.models import Host, HostMetricSnapshot


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def latest_metric_snapshots(db) -> dict[int, HostMetricSnapshot]:
    latest_times = (
        select(
            HostMetricSnapshot.host_id,
            func.max(HostMetricSnapshot.observed_at).label("latest_at"),
        )
        .group_by(HostMetricSnapshot.host_id)
        .subquery()
    )
    rows = db.scalars(
        select(HostMetricSnapshot).join(
            latest_times,
            and_(
                HostMetricSnapshot.host_id == latest_times.c.host_id,
                HostMetricSnapshot.observed_at == latest_times.c.latest_at,
            ),
        )
    ).all()
    return {row.host_id: row for row in rows}


def record_metric_snapshot(
    db,
    host: Host,
    last_snapshot: HostMetricSnapshot | None,
    interval_seconds: int,
) -> HostMetricSnapshot | None:
    observed_at = host.zabbix_last_sync_at
    if observed_at is None or interval_seconds <= 0:
        return None
    status_changed = (
        last_snapshot is None
        or last_snapshot.monitoring_status != host.monitoring_status
    )
    interval_elapsed = (
        last_snapshot is None
        or aware_utc(observed_at) - aware_utc(last_snapshot.observed_at)
        >= timedelta(seconds=interval_seconds)
    )
    if not status_changed and not interval_elapsed:
        return None
    snapshot = HostMetricSnapshot(
        host_id=host.id,
        observed_at=observed_at,
        monitoring_status=host.monitoring_status or "unknown",
        problem_count=host.problem_count or 0,
        disk_mount=host.disk_max_mount,
        disk_used_pct=host.disk_max_used_pct,
    )
    db.add(snapshot)
    return snapshot


def prune_metric_history(db, retention_days: int, now: datetime | None = None) -> None:
    if retention_days <= 0:
        return
    now = now or datetime.now(UTC)
    db.execute(
        delete(HostMetricSnapshot).where(
            HostMetricSnapshot.observed_at < now - timedelta(days=retention_days)
        )
    )
