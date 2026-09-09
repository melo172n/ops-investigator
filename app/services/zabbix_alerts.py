import logging
from uuid import uuid4

from app.integrations.chatwoot import ChatwootClient, ChatwootError
from app.schemas.zabbix import (
    NormalizedAlert,
    NotificationResult,
    ZabbixAlert,
    ZabbixWebhookResponse,
)

logger = logging.getLogger(__name__)


class ZabbixAlertService:
    def __init__(self, chatwoot: ChatwootClient) -> None:
        self._chatwoot = chatwoot

    async def handle(self, incoming: ZabbixAlert) -> ZabbixWebhookResponse:
        incident_id = f"inc_{uuid4().hex[:16]}"
        alert = self._normalize(incoming)
        content = self._format_message(incident_id, alert)

        try:
            sent = await self._chatwoot.send_operations_message(content)
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
            logger.exception(
                "Chatwoot notification failed",
                extra={"incident_id": incident_id},
            )
            notification = NotificationResult(
                status="failed",
                detail=str(exc),
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

