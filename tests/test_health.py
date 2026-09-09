import httpx

from app.core.config import Settings
from app.main import create_app


def make_settings() -> Settings:
    return Settings(zabbix_webhook_secret="test-secret")


async def test_health_returns_ok() -> None:
    app = create_app(make_settings())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
