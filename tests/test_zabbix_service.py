from datetime import UTC, datetime

from app.integrations.chatwoot import ChatwootAttempt, ChatwootMessage
from app.repositories.zabbix_alerts import RecordedAlert
from app.schemas.zabbix import ZabbixAlert
from app.services.zabbix_alerts import ZabbixAlertService


class RetryingChatwootClient:
    async def send_operations_message(self, _: str) -> ChatwootMessage:
        return ChatwootMessage(
            message_id=123,
            attempts=(
                ChatwootAttempt(status="failed", detail="HTTP 429"),
                ChatwootAttempt(status="sent", external_message_id=123),
            ),
        )


class RecordingRepository:
    def __init__(self) -> None:
        self.notifications: list[dict] = []

    async def record_alert(self, _) -> RecordedAlert:
        return RecordedAlert(incident_id="inc_test", alert_id=42)

    async def record_notification(self, **notification) -> None:
        self.notifications.append(notification)


async def test_service_persists_every_chatwoot_attempt() -> None:
    repository = RecordingRepository()
    service = ZabbixAlertService(RetryingChatwootClient(), repository)
    alert = ZabbixAlert(
        event_id="123",
        event_name="Test alert",
        severity="HIGH",
        host="chatwoot",
        status="PROBLEM",
        occurred_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
    )

    response = await service.handle(alert)

    assert response.notification.status == "sent"
    assert [item["status"] for item in repository.notifications] == [
        "failed",
        "sent",
    ]
    assert repository.notifications[1]["external_message_id"] == 123
