import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.zabbix import router as zabbix_router
from app.core.config import Settings, get_settings
from app.db.session import Database
from app.repositories.zabbix_alerts import (
    InMemoryZabbixAlertRepository,
    SqlAlchemyZabbixAlertRepository,
    ZabbixAlertRepository,
)
from app.services.investigations import LangGraphIncidentInvestigator


def create_app(
    settings: Settings | None = None,
    zabbix_alert_repository: ZabbixAlertRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    logging.basicConfig(
        level=resolved_settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    database: Database | None = None
    repository = zabbix_alert_repository
    database_url = resolved_settings.database_url.get_secret_value()
    if repository is None and database_url:
        database = Database(database_url)
        repository = SqlAlchemyZabbixAlertRepository(database.session_factory)
    elif repository is None:
        repository = InMemoryZabbixAlertRepository()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if database is not None:
            await database.dispose()

    application = FastAPI(
        title="Ops Investigator",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.zabbix_alert_repository = repository
    application.state.incident_investigator = LangGraphIncidentInvestigator(
        resolved_settings
    )
    application.include_router(zabbix_router)

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application
