from datetime import UTC, date, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Host


def active_filters(environment: str | None = None, virtual: str | None = None) -> dict[str, str]:
    values = {"environment": environment, "virtual": virtual}
    return {key: value for key, value in values.items() if value}


def distinct_values(db: Session, column) -> list[str]:
    values = db.scalars(select(column).where(column.is_not(None), column != "").distinct().order_by(column)).all()
    return [value for value in values if value]


def get_filter_options(db: Session) -> dict[str, list[str]]:
    return {"environments": distinct_values(db, Host.environment)}


def normalized_virtual_filter(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    return normalized if normalized in {"YES", "NO"} else None


def apply_host_filters(stmt: Select, environment: str | None = None, virtual: str | None = None) -> Select:
    if environment:
        stmt = stmt.where(Host.environment == environment.upper())
    active_virtual = normalized_virtual_filter(virtual)
    if active_virtual == "YES":
        stmt = stmt.where(Host.virtual.is_(True))
    elif active_virtual == "NO":
        stmt = stmt.where(Host.virtual.is_(False))
    return stmt


def support_status_label(support_end_date: date | None) -> str:
    if support_end_date is None:
        return "not set"
    today = datetime.now(UTC).date()
    if support_end_date < today:
        return "expired"
    if (support_end_date - today).days <= 180:
        return "expires soon"
    return "active"
