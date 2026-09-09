import logging

from fastapi import FastAPI

from app.api.zabbix import router as zabbix_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    logging.basicConfig(
        level=resolved_settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    application = FastAPI(
        title="Ops Investigator",
        version="0.1.0",
    )
    application.state.settings = resolved_settings
    application.include_router(zabbix_router)

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application
