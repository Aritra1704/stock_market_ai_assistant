from src.models.notification import DeviceRegistration, NotificationPayload
from src.notifications.service import NotificationService


def test_register_and_send_notification() -> None:
    service = NotificationService()
    service.register_device(DeviceRegistration(user_id="u1", platform="android", token="t-android"))
    service.register_device(DeviceRegistration(user_id="u1", platform="ios", token="t-ios"))

    result = service.send_to_user(
        "u1",
        NotificationPayload(title="Alert", body="Check portfolio", data={"risk": "high"}),
    )

    assert result["user_id"] == "u1"
    assert len(result["results"]) >= 1
