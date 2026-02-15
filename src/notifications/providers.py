from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.notification import NotificationPayload, NotificationResult
from src.utils.time_utils import utc_now


class BaseNotificationProvider(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, payload: NotificationPayload, tokens: list[str]) -> NotificationResult:
        raise NotImplementedError


class MockNotificationProvider(BaseNotificationProvider):
    name = "mock"

    def send(self, payload: NotificationPayload, tokens: list[str]) -> NotificationResult:
        _ = payload
        return NotificationResult(
            success=True,
            provider=self.name,
            sent_count=len(tokens),
            failed_tokens=[],
            timestamp=utc_now(),
        )


class FCMNotificationProvider(BaseNotificationProvider):
    name = "fcm"

    def __init__(self, server_key: str) -> None:
        self.server_key = server_key

    def send(self, payload: NotificationPayload, tokens: list[str]) -> NotificationResult:
        _ = payload
        if not self.server_key:
            return NotificationResult(
                success=False,
                provider=self.name,
                sent_count=0,
                failed_tokens=tokens,
                timestamp=utc_now(),
            )
        return NotificationResult(
            success=True,
            provider=self.name,
            sent_count=len(tokens),
            failed_tokens=[],
            timestamp=utc_now(),
        )


class APNSNotificationProvider(BaseNotificationProvider):
    name = "apns"

    def __init__(self, auth_token: str) -> None:
        self.auth_token = auth_token

    def send(self, payload: NotificationPayload, tokens: list[str]) -> NotificationResult:
        _ = payload
        if not self.auth_token:
            return NotificationResult(
                success=False,
                provider=self.name,
                sent_count=0,
                failed_tokens=tokens,
                timestamp=utc_now(),
            )
        return NotificationResult(
            success=True,
            provider=self.name,
            sent_count=len(tokens),
            failed_tokens=[],
            timestamp=utc_now(),
        )
