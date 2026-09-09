import httpx

from app.core.config import Settings
from app.main import create_app


def make_app():
    settings = Settings(
        zabbix_webhook_secret="test-secret",
        chatwoot_enabled=False,
    )
    return create_app(settings)


def alert_payload() -> dict[str, str]:
    return {
        "event_id": "123456",
        "event_name": "Chatwoot indisponível",
        "severity": "HIGH",
        "host": "chatwoot",
        "status": "PROBLEM",
        "occurred_at": "2026-09-09T14:02:00Z",
        "description": "Health check falhou",
    }


async def test_rejects_invalid_secret() -> None:
    transport = httpx.ASGITransport(app=make_app())

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/webhooks/zabbix",
            headers={"X-Webhook-Secret": "wrong"},
            json=alert_payload(),
        )

    assert response.status_code == 401


async def test_accepts_alert_and_normalizes_it() -> None:
    transport = httpx.ASGITransport(app=make_app())

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/webhooks/zabbix",
            headers={"X-Webhook-Secret": "test-secret"},
            json=alert_payload(),
        )

    assert response.status_code == 202
    body = response.json()
    assert body["incident_id"].startswith("inc_")
    assert body["alert"]["source"] == "zabbix"
    assert body["alert"]["source_event_id"] == "123456"
    assert body["alert"]["severity"] == "high"
    assert body["notification"] == {
        "channel": "whatsapp",
        "status": "skipped",
        "external_message_id": None,
        "detail": "CHATWOOT_ENABLED=false",
    }

