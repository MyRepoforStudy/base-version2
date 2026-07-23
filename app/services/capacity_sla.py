from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class CapacityForecast:
    status: str
    mount_point: str | None
    current_pct: float | None
    daily_growth_pct: float | None
    forecast_at: datetime | None
    days_remaining: int | None
    sample_count: int
    span_days: float


@dataclass(frozen=True)
class AvailabilitySla:
    status: str
    availability_pct: float | None
    coverage_pct: float
    available_hours: float
    observed_hours: float
    sample_count: int


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def capacity_forecast(
    snapshots,
    current_pct: float | None,
    mount_point: str | None,
    target_pct: float = 95.0,
    now: datetime | None = None,
) -> CapacityForecast:
    now = now or datetime.now(UTC)
    points = sorted(
        (
            (_aware_utc(snapshot.observed_at), float(snapshot.disk_used_pct))
            for snapshot in snapshots
            if snapshot.disk_used_pct is not None
            and snapshot.disk_mount == mount_point
            and 0 <= float(snapshot.disk_used_pct) <= 100
        ),
        key=lambda point: point[0],
    )
    span_days = (
        (points[-1][0] - points[0][0]).total_seconds() / 86400
        if len(points) >= 2
        else 0.0
    )
    base_result = {
        "mount_point": mount_point,
        "current_pct": current_pct,
        "sample_count": len(points),
        "span_days": round(span_days, 1),
    }
    if current_pct is None or mount_point is None:
        return CapacityForecast(
            status="unknown",
            daily_growth_pct=None,
            forecast_at=None,
            days_remaining=None,
            **base_result,
        )
    if current_pct >= target_pct:
        return CapacityForecast(
            status="critical",
            daily_growth_pct=None,
            forecast_at=now,
            days_remaining=0,
            **base_result,
        )
    if len(points) < 6 or span_days < 1:
        return CapacityForecast(
            status="collecting",
            daily_growth_pct=None,
            forecast_at=None,
            days_remaining=None,
            **base_result,
        )

    origin = points[0][0]
    x_values = [(timestamp - origin).total_seconds() / 86400 for timestamp, _ in points]
    y_values = [value for _, value in points]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((value - x_mean) ** 2 for value in x_values)
    slope = (
        sum(
            (x_value - x_mean) * (y_value - y_mean)
            for x_value, y_value in zip(x_values, y_values, strict=True)
        )
        / denominator
        if denominator
        else 0.0
    )
    slope = round(slope, 3)
    if slope <= 0.05:
        return CapacityForecast(
            status="stable",
            daily_growth_pct=slope,
            forecast_at=None,
            days_remaining=None,
            **base_result,
        )

    days_remaining = max(0, round((target_pct - current_pct) / slope))
    forecast_at = now + timedelta(days=days_remaining)
    if days_remaining <= 7:
        status = "critical"
    elif days_remaining <= 30:
        status = "warning"
    elif days_remaining <= 90:
        status = "watch"
    else:
        status = "healthy"
    return CapacityForecast(
        status=status,
        daily_growth_pct=slope,
        forecast_at=forecast_at,
        days_remaining=days_remaining,
        **base_result,
    )


def availability_sla(
    snapshots,
    target_percent: float = 99.9,
    window_days: int = 30,
    max_gap_seconds: int = 7200,
    now: datetime | None = None,
) -> AvailabilitySla:
    now = now or datetime.now(UTC)
    window_start = now - timedelta(days=window_days)
    available_statuses = {"ok", "problem", "available"}
    unavailable_statuses = {"down", "unavailable", "disabled"}
    known_statuses = available_statuses | unavailable_statuses
    ordered = sorted(
        (
            snapshot
            for snapshot in snapshots
            if (snapshot.monitoring_status or "unknown").lower() in known_statuses
        ),
        key=lambda snapshot: _aware_utc(snapshot.observed_at),
    )
    known_seconds = 0.0
    available_seconds = 0.0

    for index, snapshot in enumerate(ordered):
        observed_at = _aware_utc(snapshot.observed_at)
        next_at = (
            _aware_utc(ordered[index + 1].observed_at)
            if index + 1 < len(ordered)
            else now
        )
        start_at = max(observed_at, window_start)
        end_at = min(next_at, now, observed_at + timedelta(seconds=max_gap_seconds))
        if end_at <= start_at:
            continue
        duration = (end_at - start_at).total_seconds()
        known_seconds += duration
        if (snapshot.monitoring_status or "unknown").lower() in available_statuses:
            available_seconds += duration

    window_seconds = max(1.0, (now - window_start).total_seconds())
    coverage_pct = min(100.0, known_seconds / window_seconds * 100)
    availability_pct = (
        available_seconds / known_seconds * 100
        if known_seconds > 0
        else None
    )
    if availability_pct is None or coverage_pct < 95:
        status = "collecting"
    elif availability_pct >= target_percent:
        status = "met"
    else:
        status = "missed"
    return AvailabilitySla(
        status=status,
        availability_pct=round(availability_pct, 3) if availability_pct is not None else None,
        coverage_pct=round(coverage_pct, 1),
        available_hours=round(available_seconds / 3600, 1),
        observed_hours=round(known_seconds / 3600, 1),
        sample_count=len(ordered),
    )
