from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AlertEvent, Incident, NotificationAttempt
from app.schemas.zabbix import NormalizedAlert


@dataclass(frozen=True)
class RecordedAlert:
    incident_id: str
    alert_id: int
    duplicate: bool = False


class ZabbixAlertRepository(Protocol):
    async def record_alert(self, alert: NormalizedAlert) -> RecordedAlert: ...

    async def record_notification(
        self,
        *,
        alert_id: int,
        channel: str,
        status: str,
        external_message_id: int | None,
        detail: str | None,
    ) -> None: ...


class InMemoryZabbixAlertRepository:
    def __init__(self) -> None:
        self._incidents: dict[tuple[str, str], str] = {}
        self._alerts: dict[tuple[str, str, str], RecordedAlert] = {}
        self._next_alert_id = 1

    async def record_alert(self, alert: NormalizedAlert) -> RecordedAlert:
        incident_key = (alert.source, alert.source_event_id)
        incident_id = self._incidents.setdefault(
            incident_key,
            f"inc_{uuid4().hex[:16]}",
        )
        alert_key = (*incident_key, alert.status)
        existing = self._alerts.get(alert_key)
        if existing is not None:
            return RecordedAlert(
                incident_id=existing.incident_id,
                alert_id=existing.alert_id,
                duplicate=True,
            )

        recorded = RecordedAlert(
            incident_id=incident_id,
            alert_id=self._next_alert_id,
        )
        self._next_alert_id += 1
        self._alerts[alert_key] = recorded
        return recorded

    async def record_notification(
        self,
        *,
        alert_id: int,
        channel: str,
        status: str,
        external_message_id: int | None,
        detail: str | None,
    ) -> None:
        return None


class SqlAlchemyZabbixAlertRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def record_alert(self, alert: NormalizedAlert) -> RecordedAlert:
        async with self._session_factory() as session:
            try:
                async with session.begin():
                    existing = await self._find_alert(session, alert)
                    if existing is not None:
                        return RecordedAlert(
                            incident_id=existing.incident_id,
                            alert_id=existing.id,
                            duplicate=True,
                        )

                    incident = await self._find_incident(session, alert)
                    if incident is None:
                        incident = Incident(
                            id=f"inc_{uuid4().hex[:16]}",
                            source=alert.source,
                            source_event_id=alert.source_event_id,
                            service=alert.service,
                            title=alert.title,
                            severity=alert.severity,
                            current_status=alert.status,
                            opened_at=alert.occurred_at,
                            resolved_at=(
                                alert.occurred_at
                                if self._is_resolved(alert.status)
                                else None
                            ),
                        )
                        session.add(incident)
                    else:
                        incident.service = alert.service
                        incident.title = alert.title
                        incident.severity = alert.severity
                        incident.current_status = alert.status
                        incident.resolved_at = (
                            alert.occurred_at
                            if self._is_resolved(alert.status)
                            else None
                        )

                    event = AlertEvent(
                        incident_id=incident.id,
                        source=alert.source,
                        source_event_id=alert.source_event_id,
                        status=alert.status,
                        occurred_at=alert.occurred_at,
                        description=alert.description,
                        tags={},
                    )
                    session.add(event)
                    await session.flush()
                    recorded = RecordedAlert(
                        incident_id=incident.id,
                        alert_id=event.id,
                    )
            except IntegrityError:
                await session.rollback()
                duplicate = await self._find_alert(session, alert)
                if duplicate is None:
                    raise
                return RecordedAlert(
                    incident_id=duplicate.incident_id,
                    alert_id=duplicate.id,
                    duplicate=True,
                )

            return recorded

    async def record_notification(
        self,
        *,
        alert_id: int,
        channel: str,
        status: str,
        external_message_id: int | None,
        detail: str | None,
    ) -> None:
        async with self._session_factory.begin() as session:
            session.add(
                NotificationAttempt(
                    alert_event_id=alert_id,
                    channel=channel,
                    status=status,
                    external_message_id=(
                        str(external_message_id)
                        if external_message_id is not None
                        else None
                    ),
                    detail=detail,
                )
            )

    @staticmethod
    async def _find_incident(
        session: AsyncSession,
        alert: NormalizedAlert,
    ) -> Incident | None:
        result = await session.execute(
            select(Incident).where(
                Incident.source == alert.source,
                Incident.source_event_id == alert.source_event_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _find_alert(
        session: AsyncSession,
        alert: NormalizedAlert,
    ) -> AlertEvent | None:
        result = await session.execute(
            select(AlertEvent).where(
                AlertEvent.source == alert.source,
                AlertEvent.source_event_id == alert.source_event_id,
                AlertEvent.status == alert.status,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _is_resolved(status: str) -> bool:
        return status in {"OK", "RESOLVED"}
