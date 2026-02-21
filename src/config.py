from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus


SUPPORTED_APP_ENVS = {"SIT", "UAT"}


def _current_app_env() -> str:
    default_env = "UAT" if os.getenv("RAILWAY_ENVIRONMENT", "").strip() else "SIT"
    raw = os.getenv("APP_ENV", default_env).strip().upper()
    if not raw:
        return default_env
    if raw not in SUPPORTED_APP_ENVS:
        raise ValueError(f"Invalid APP_ENV: {raw}. Supported values: {sorted(SUPPORTED_APP_ENVS)}")
    return raw


def _get_first_set(*env_names: str) -> str:
    for env_name in env_names:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return ""


def _normalize_database_url(raw_url: str) -> str:
    if not raw_url:
        return raw_url
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("postgresql://") and "+" not in raw_url.split("://", 1)[0]:
        return raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("postgresql+psycopg://"):
        return raw_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    return raw_url


def _with_sslmode_if_needed(db_url: str) -> str:
    if not db_url or "sslmode=" in db_url:
        return db_url
    lowered = db_url.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered:
        return db_url
    sep = "&" if "?" in db_url else "?"
    return f"{db_url}{sep}sslmode=require"


def _build_database_url() -> str:
    app_env = _current_app_env()
    if app_env == "UAT":
        explicit = _get_first_set("UAT_DATABASE_URL", "DATABASE_URL", "DATABASE_PUBLIC_URL")
        host = _get_first_set("UAT_PGHOST", "PGHOST")
        port = _get_first_set("UAT_PGPORT", "PGPORT") or "5432"
        user = _get_first_set("UAT_PGUSER", "PGUSER")
        password = _get_first_set("UAT_PGPASSWORD", "PGPASSWORD")
        database = _get_first_set("UAT_PGDATABASE", "PGDATABASE")
    else:
        explicit = _get_first_set("SIT_DATABASE_URL", "DATABASE_URL", "DATABASE_PUBLIC_URL")
        host = _get_first_set("SIT_PGHOST", "PGHOST")
        port = _get_first_set("SIT_PGPORT", "PGPORT") or "5432"
        user = _get_first_set("SIT_PGUSER", "PGUSER")
        password = _get_first_set("SIT_PGPASSWORD", "PGPASSWORD")
        database = _get_first_set("SIT_PGDATABASE", "PGDATABASE")

    if explicit:
        return _with_sslmode_if_needed(_normalize_database_url(explicit))

    if host and user and database:
        pwd = quote_plus(password)
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{database}"
        return _with_sslmode_if_needed(url)

    # Local dev fallback when DATABASE_URL is not set.
    sqlite_file = Path(os.getenv("SQLITE_DB_PATH", "./app.db")).as_posix()
    if sqlite_file.startswith("/"):
        return f"sqlite:///{sqlite_file}"
    return f"sqlite:///./{sqlite_file.lstrip('./')}"


def _build_db_schema() -> str:
    app_env = _current_app_env()
    if app_env == "UAT":
        return _get_first_set("UAT_DB_SCHEMA", "DB_SCHEMA") or "stock_ai_lab"
    return _get_first_set("SIT_DB_SCHEMA", "DB_SCHEMA") or "stock_ai_lab"


@dataclass(frozen=True)
class Settings:
    app_env: str = _current_app_env()
    app_name: str = os.getenv("APP_NAME", "stock_market_ai_assistant")
    app_debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8004"))

    database_url: str = _build_database_url()
    db_schema: str = _build_db_schema()

    intraday_daily_budget_inr: float = float(os.getenv("INTRADAY_DAILY_BUDGET_INR", "100"))
    intraday_max_open_positions: int = int(os.getenv("INTRADAY_MAX_OPEN_POSITIONS", "1"))

    swing_allocation_inr: float = float(os.getenv("SWING_ALLOCATION_INR", "1000"))
    swing_max_open_positions: int = int(os.getenv("SWING_MAX_OPEN_POSITIONS", "2"))
    swing_default_horizon_days: int = int(os.getenv("SWING_DEFAULT_HORIZON_DAYS", "20"))
    max_stocks_per_mode: int = int(os.getenv("MAX_STOCKS_PER_MODE", "10"))

    audit_top_stocks_limit: int = int(os.getenv("AUDIT_TOP_STOCKS_LIMIT", "100"))
    audit_retention_days: int = int(os.getenv("AUDIT_RETENTION_DAYS", "15"))
    audit_cleanup_interval_minutes: int = int(os.getenv("AUDIT_CLEANUP_INTERVAL_MINUTES", "360"))
    audit_cleanup_scheduler_enabled: bool = os.getenv("AUDIT_CLEANUP_SCHEDULER_ENABLED", "true").lower() == "true"
    audit_universe_csv_url: str = os.getenv(
        "AUDIT_UNIVERSE_CSV_URL",
        "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
    )
    audit_universe_timeout_seconds: int = int(os.getenv("AUDIT_UNIVERSE_TIMEOUT_SECONDS", "20"))

    notification_provider: str = os.getenv("NOTIFICATION_PROVIDER", "mock").strip().lower()
    fcm_server_key: str = os.getenv("FCM_SERVER_KEY", "")
    apns_auth_token: str = os.getenv("APNS_AUTH_TOKEN", "")


settings = Settings()


def get_settings() -> Settings:
    return settings
