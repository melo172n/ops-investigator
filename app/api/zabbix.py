from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import Settings
from app.integrations.chatwoot import ChatwootClient
from app.schemas.zabbix import ZabbixAlert, ZabbixWebhookResponse
from app.services.zabbix_alerts import ZabbixAlertService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/zabbix",
    response_model=ZabbixWebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_zabbix_alert(
    payload: ZabbixAlert,
    request: Request,
    webhook_secret: Annotated[
        str | None,
        Header(alias="X-Webhook-Secret"),
    ] = None,
) -> ZabbixWebhookResponse:
    settings: Settings = request.app.state.settings
    expected = settings.zabbix_webhook_secret.get_secret_value()

    if not webhook_secret or not compare_digest(webhook_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook secret inválido",
        )

    service = ZabbixAlertService(ChatwootClient(settings))
    return await service.handle(payload)

