import logging

from app.integrations.chatwoot import (
    ChatwootAttempt,
    ChatwootClient,
    ChatwootError,
)
from app.repositories.zabbix_alerts import ZabbixAlertRepository
from app.schemas.zabbix import (
    NormalizedAlert,
    NotificationResult,
    ZabbixAlert,
    ZabbixWebhookResponse,
)

logger = logging.getLogger(__name__)


class ZabbixAlertService:
    def __init__(
        self,
        chatwoot: ChatwootClient,
        repository: ZabbixAlertRepository,
    ) -> None:
        self._chatwoot = chatwoot
        self._repository = repository

    async def handle(self, incoming: ZabbixAlert) -> ZabbixWebhookResponse:
        alert = self._normalize(incoming)
        recorded = await self._repository.record_alert(alert)
        incident_id = recorded.incident_id

        if recorded.duplicate:
            return ZabbixWebhookResponse(
                incident_id=incident_id,
                alert=alert,
                notification=NotificationResult(
                    status="skipped",
                    detail="duplicate alert event",
                ),
            )

        content = self._format_message(incident_id, alert)
        attempts: tuple[ChatwootAttempt, ...] = ()

        try:
            sent = await self._chatwoot.send_operations_message(content)
            attempts = sent.attempts
            if sent.skipped:
                notification = NotificationResult(
                    status="skipped",
                    detail="CHATWOOT_ENABLED=false",
                )
            else:
                notification = NotificationResult(
                    status="sent",
                    external_message_id=sent.message_id,
                )
        except ChatwootError as exc:
            attempts = exc.attempts
            logger.exception(
                "chatwoot_notification status=failed incident_id=%s "
                "source_event_id=%s alert_status=%s attempts=%s",
                incident_id,
                alert.source_event_id,
                alert.status,
                len(attempts),
            )
            notification = NotificationResult(
                status="failed",
                detail=str(exc),
            )

        if not attempts:
            attempts = (
                ChatwootAttempt(
                    status=notification.status,
                    external_message_id=notification.external_message_id,
                    detail=notification.detail,
                ),
            )

        for attempt in attempts:
            await self._repository.record_notification(
                alert_id=recorded.alert_id,
                channel=notification.channel,
                status=attempt.status,
                external_message_id=attempt.external_message_id,
                detail=attempt.detail,
            )

        return ZabbixWebhookResponse(
            incident_id=incident_id,
            alert=alert,
            notification=notification,
        )

    @staticmethod
    def _normalize(incoming: ZabbixAlert) -> NormalizedAlert:
        return NormalizedAlert(
            source_event_id=incoming.event_id,
            service=incoming.host,
            title=incoming.event_name,
            severity=incoming.severity.lower(),
            status=incoming.status.upper(),
            occurred_at=incoming.occurred_at,
            description=incoming.description,
        )

    @staticmethod
    def _format_message(incident_id: str, alert: NormalizedAlert) -> str:
        lines = [
            "🚨 Alerta operacional",
            "",
            f"Serviço: {alert.service}",
            f"Severidade: {alert.severity}",
            f"Status: {alert.status}",
            f"Horário: {alert.occurred_at.isoformat()}",
            "",
            f"Resumo: {alert.title}",
        ]
        if alert.description:
            lines.append(f"Detalhes: {alert.description}")
        lines.extend(["", f"Incidente: {incident_id}"])
        return "\n".join(lines)
