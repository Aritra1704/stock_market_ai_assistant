import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Stock Market AI Assistant")
    app_debug: bool = os.getenv("APP_DEBUG", "true").lower() == "true"
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    zerodha_api_key: str = os.getenv("ZERODHA_API_KEY", os.getenv("ZEROHDA_API_KEY", ""))
    zerodha_access_token: str = os.getenv("ZERODHA_ACCESS_TOKEN", "")

    notification_provider: str = os.getenv("NOTIFICATION_PROVIDER", "mock")
    fcm_server_key: str = os.getenv("FCM_SERVER_KEY", "")
    apns_auth_token: str = os.getenv("APNS_AUTH_TOKEN", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
