from __future__ import annotations

from src.config import get_settings
from src.models.notification import DeviceRegistration, NotificationPayload
from src.notifications.providers import (
    APNSNotificationProvider,
    BaseNotificationProvider,
    FCMNotificationProvider,
    MockNotificationProvider,
)
from src.storage.repository import DeviceRepository


class NotificationService:
    def __init__(self, repository: DeviceRepository | None = None) -> None:
        settings = get_settings()
        self.repository = repository or DeviceRepository()
        self.default_provider = settings.notification_provider
        self.providers: dict[str, BaseNotificationProvider] = {
            "mock": MockNotificationProvider(),
            "fcm": FCMNotificationProvider(settings.fcm_server_key),
            "apns": APNSNotificationProvider(settings.apns_auth_token),
        }

    def register_device(self, registration: DeviceRegistration) -> dict:
        self.repository.register(registration.user_id, registration.platform, registration.token)
        return {"status": "registered", "user_id": registration.user_id, "platform": registration.platform}

    def send_to_user(self, user_id: str, payload: NotificationPayload) -> dict:
        provider_key = self.default_provider
        provider = self.providers.get(provider_key, self.providers["mock"])

        android_tokens = self.repository.list_tokens(user_id, "android")
        ios_tokens = self.repository.list_tokens(user_id, "ios")

        results = []
        if android_tokens:
            android_provider = self.providers.get("fcm", provider)
            results.append(android_provider.send(payload, android_tokens).model_dump())
        if ios_tokens:
            ios_provider = self.providers.get("apns", provider)
            results.append(ios_provider.send(payload, ios_tokens).model_dump())

        if not results:
            fallback_tokens = self.repository.list_tokens(user_id)
            results.append(provider.send(payload, fallback_tokens).model_dump())

        return {"user_id": user_id, "results": results}
