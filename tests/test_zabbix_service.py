from datetime import UTC, datetime

from app.integrations.chatwoot import ChatwootAttempt, ChatwootMessage
from app.repositories.zabbix_alerts import RecordedAlert
from app.schemas.investigation import (
    IncidentContext,
    InvestigationOutcome,
    InvestigationReport,
)
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


class RecordingChatwootClient:
    def __init__(self) -> None:
        self.content = ""

    async def send_operations_message(self, content: str) -> ChatwootMessage:
        self.content = content
        return ChatwootMessage(message_id=123)


class ConfirmedInvestigator:
    async def investigate(self, _: IncidentContext) -> InvestigationReport:
        return InvestigationReport(
            incident_id="inc_test",
            outcome=InvestigationOutcome.CONFIRMED,
            facts=[],
            hypothesis="Chatwoot não conseguiu se comunicar com o bridge.",
            confidence=0.8,
            next_check="Verificar os logs do bridge.",
            sources_consulted=["loki"],
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


async def test_service_includes_the_investigation_in_the_notification() -> None:
    repository = RecordingRepository()
    chatwoot = RecordingChatwootClient()
    service = ZabbixAlertService(
        chatwoot,
        repository,
        ConfirmedInvestigator(),
    )
    alert = ZabbixAlert(
        event_id="123",
        event_name="Test alert",
        severity="HIGH",
        host="chatwoot",
        status="PROBLEM",
        occurred_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
    )

    await service.handle(alert)

    assert "Conclusão: confirmed" in chatwoot.content
    assert "Hipótese: Chatwoot não conseguiu" in chatwoot.content
    assert "Próxima verificação: Verificar os logs do bridge." in chatwoot.content
