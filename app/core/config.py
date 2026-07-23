from functools import lru_cache
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Resolve relative to this file, not the process cwd - the app must work the
# same whether it's launched from the repo root or from elsewhere.
BASE_DIR = Path(__file__).resolve().parents[2]


def env_bool(name: str, default: bool = True) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def env_int(name: str, default: int) -> int:
    value = getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    value = getenv(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


class Settings:
    app_name: str = getenv("APP_NAME", "Linux Server Inventory")
    app_env: str = getenv("APP_ENV", "local")
    app_timezone: str = getenv("APP_TIMEZONE", "Asia/Almaty")
    session_secret: str = getenv("SESSION_SECRET", "change-me-admin-session-secret")
    admin_username: str = getenv("ADMIN_USERNAME", "admin")
    admin_password: str = getenv("ADMIN_PASSWORD", "admin")
    database_url: str = getenv(
        "DATABASE_URL",
        "postgresql+psycopg://server_inventory:server_inventory@localhost:5432/server_inventory",
    )
    static_dir: str = getenv("STATIC_DIR", str(BASE_DIR / "app" / "static"))
    templates_dir: str = getenv("TEMPLATES_DIR", str(BASE_DIR / "app" / "templates"))
    zabbix_url: str | None = getenv("ZABBIX_URL")
    zabbix_api_token: str | None = getenv("ZABBIX_API_TOKEN")
    zabbix_verify_ssl: bool = env_bool("ZABBIX_VERIFY_SSL", True)
    zabbix_ca_file: str | None = getenv("ZABBIX_CA_FILE")
    zabbix_host_group: str = getenv("ZABBIX_HOST_GROUP", "Linux servers")
    zabbix_auto_refresh_seconds: int = env_int("ZABBIX_AUTO_REFRESH_SECONDS", 300)
    zabbix_history_backfill_days: int = env_int("ZABBIX_HISTORY_BACKFILL_DAYS", 30)
    metric_history_interval_seconds: int = env_int("METRIC_HISTORY_INTERVAL_SECONDS", 3600)
    metric_history_retention_days: int = env_int("METRIC_HISTORY_RETENTION_DAYS", 90)
    sla_target_percent: float = env_float("SLA_TARGET_PERCENT", 99.9)
    capacity_forecast_target_percent: float = env_float(
        "CAPACITY_FORECAST_TARGET_PERCENT",
        95.0,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
