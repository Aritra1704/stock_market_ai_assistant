from datetime import datetime
from pydantic import BaseModel, Field


class DeviceRegistration(BaseModel):
    user_id: str
    platform: str = Field(pattern="^(android|ios)$")
    token: str


class NotificationPayload(BaseModel):
    title: str
    body: str
    data: dict[str, str] = {}


class NotificationResult(BaseModel):
    success: bool
    provider: str
    sent_count: int
    failed_tokens: list[str] = []
    timestamp: datetime
