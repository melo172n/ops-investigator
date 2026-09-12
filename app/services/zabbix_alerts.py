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
from app.schemas.investigation import IncidentContext, InvestigationReport
from app.services.investigations import IncidentInvestigator

logger = logging.getLogger(__name__)


class ZabbixAlertService:
    def __init__(
        self,
        chatwoot: ChatwootClient,
        repository: ZabbixAlertRepository,
        investigator: IncidentInvestigator | None = None,
    ) -> None:
        self._chatwoot = chatwoot
        self._repository = repository
        self._investigator = investigator

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

        report = await self._investigate(incident_id, alert)
        content = self._format_message(incident_id, alert, report)
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

    async def _investigate(
        self,
        incident_id: str,
        alert: NormalizedAlert,
    ) -> InvestigationReport | None:
        if self._investigator is None:
            return None
        return await self._investigator.investigate(
            IncidentContext(
                incident_id=incident_id,
                service=alert.service,
                title=alert.title,
                severity=alert.severity,
                status=alert.status,
                occurred_at=alert.occurred_at,
                description=alert.description,
            )
        )

    @staticmethod
    def _format_message(
        incident_id: str,
        alert: NormalizedAlert,
        report: InvestigationReport | None,
    ) -> str:
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
        if report is not None:
            lines.extend(["", f"Conclusão: {report.outcome}"])
            if report.hypothesis:
                lines.append(f"Hipótese: {report.hypothesis}")
            if report.facts:
                lines.append("Evidências:")
                lines.extend(f"- {fact.text}" for fact in report.facts)
            lines.append(f"Próxima verificação: {report.next_check}")
        lines.extend(["", f"Incidente: {incident_id}"])
        return "\n".join(lines)
