from datetime import UTC, datetime

from sqlalchemy import func, select, text

from app.db.base import Base
from app.db.models import AlertEvent, Incident, NotificationAttempt
from app.db.session import Database
from app.repositories.zabbix_alerts import SqlAlchemyZabbixAlertRepository
from app.schemas.zabbix import NormalizedAlert


def make_alert(status: str = "PROBLEM") -> NormalizedAlert:
    return NormalizedAlert(
        source_event_id="6498",
        service="TecnoCW VPS Production",
        title="Ops Investigator integration test",
        severity="warning",
        status=status,
        occurred_at=datetime(2026, 9, 10, 14, 30, tzinfo=UTC),
    )


async def test_repository_persists_lifecycle_and_notification() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    async with database.engine.begin() as connection:
        await connection.execute(text("PRAGMA foreign_keys=ON"))
        await connection.run_sync(Base.metadata.create_all)

    repository = SqlAlchemyZabbixAlertRepository(database.session_factory)
    problem = await repository.record_alert(make_alert())
    duplicate = await repository.record_alert(make_alert())
    recovery = await repository.record_alert(make_alert("RESOLVED"))
    await repository.record_notification(
        alert_id=problem.alert_id,
        channel="whatsapp",
        status="sent",
        external_message_id=236,
        detail=None,
    )

    assert duplicate.duplicate is True
    assert recovery.incident_id == problem.incident_id

    async with database.session_factory() as session:
        incident = await session.get(Incident, problem.incident_id)
        alert_count = await session.scalar(
            select(func.count()).select_from(AlertEvent)
        )
        notification_count = await session.scalar(
            select(func.count()).select_from(NotificationAttempt)
        )

    assert incident is not None
    assert incident.current_status == "RESOLVED"
    assert incident.resolved_at is not None
    assert alert_count == 2
    assert notification_count == 1

    await database.dispose()
