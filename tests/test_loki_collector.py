from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.loki import (
    LokiCollectionError,
    LokiConfigurationError,
    LokiEvidenceCollector,
)
from app.schemas.investigation import IncidentContext


INCIDENT_TIME = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def loki_settings(**overrides) -> Settings:
    values = {
        "zabbix_webhook_secret": "test-secret",
        "loki_url": "https://loki.example.com",
        "loki_bearer_token": "test-token",
        "loki_tenant_id": "tenant-1",
        "loki_queries_by_service": {
            "chatwoot": '{container=~"chatwoot.*"} |= "error"'
        },
    }
    values.update(overrides)
    return Settings(**values)


def incident(service: str = "chatwoot") -> IncidentContext:
    return IncidentContext(
        incident_id="inc_test",
        service=service,
        title="Elevated error rate",
        severity="high",
        status="PROBLEM",
        occurred_at=INCIDENT_TIME,
    )


def loki_response(values=None) -> dict:
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {"container": "chatwoot"},
                    "values": values
                    or [
                        [
                            "1789128060000000000",
                            "Database connection failed",
                        ]
                    ],
                }
            ],
        },
    }


async def test_queries_bounded_range_with_authentication_headers() -> None:
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=loki_response())

    collector = LokiEvidenceCollector(
        loki_settings(),
        transport=httpx.MockTransport(handler),
    )

    result = await collector.collect(incident())

    assert captured_request is not None
    assert captured_request.url.path == "/loki/api/v1/query_range"
    params = captured_request.url.params
    assert params["query"] == '{container=~"chatwoot.*"} |= "error"'
    assert params["start"] == "1789127100000000000"
    assert params["end"] == "1789128900000000000"
    assert params["limit"] == "100"
    assert params["direction"] == "forward"
    assert captured_request.headers["Authorization"] == "Bearer test-token"
    assert captured_request.headers["X-Scope-OrgID"] == "tenant-1"
    assert result.sources_consulted == ["loki"]
    assert len(result.items) == 1


async def test_orders_entries_and_creates_unique_stable_references() -> None:
    values = [
        ["1789128120000000000", "Second error"],
        ["1789128060000000000", "First error"],
        ["1789128060000000000", "Different error at same time"],
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=loki_response(values))

    collector = LokiEvidenceCollector(
        loki_settings(),
        transport=httpx.MockTransport(handler),
    )

    result = await collector.collect(incident())

    assert [item.summary for item in result.items] == [
        "First error",
        "Different error at same time",
        "Second error",
    ]
    references = [item.reference for item in result.items]
    assert len(set(references)) == 3
    assert all(reference.startswith("loki:") for reference in references)


async def test_redacts_secrets_and_customer_identifiers() -> None:
    unsafe_line = (
        "authorization=Bearer abc.def token=top-secret "
        "content=customer-text user@example.com +55 11 99999-9999"
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=loki_response([["1789128060000000000", unsafe_line]]),
        )

    collector = LokiEvidenceCollector(
        loki_settings(),
        transport=httpx.MockTransport(handler),
    )

    result = await collector.collect(incident())
    serialized = result.model_dump_json()

    assert "abc.def" not in serialized
    assert "top-secret" not in serialized
    assert "customer-text" not in serialized
    assert "user@example.com" not in serialized
    assert "99999-9999" not in serialized
    assert "[REDACTED]" in result.items[0].summary


async def test_redacts_nested_sensitive_json_fields() -> None:
    unsafe_line = (
        '{"level":"error","content":"customer private message",'
        '"context":{"token":"secret-token","detail":"database failed"}}'
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=loki_response([["1789128060000000000", unsafe_line]]),
        )

    collector = LokiEvidenceCollector(
        loki_settings(),
        transport=httpx.MockTransport(handler),
    )

    result = await collector.collect(incident())
    summary = result.items[0].summary

    assert "customer private message" not in summary
    assert "secret-token" not in summary
    assert "database failed" in summary


async def test_requires_an_explicit_query_for_each_service() -> None:
    collector = LokiEvidenceCollector(loki_settings())

    with pytest.raises(LokiConfigurationError, match="unknown-service"):
        await collector.collect(incident("unknown-service"))


async def test_rejects_query_without_stream_selector() -> None:
    collector = LokiEvidenceCollector(
        loki_settings(loki_queries_by_service={"chatwoot": '|= "error"'})
    )

    with pytest.raises(LokiConfigurationError, match="seletor"):
        await collector.collect(incident())


def test_rejects_query_window_larger_than_sixty_minutes() -> None:
    with pytest.raises(ValidationError, match="60 minutos"):
        loki_settings(
            loki_window_before_minutes=31,
            loki_window_after_minutes=30,
        )


async def test_sanitizes_http_error_details() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="secret upstream detail")

    collector = LokiEvidenceCollector(
        loki_settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LokiCollectionError) as raised:
        await collector.collect(incident())

    assert "HTTP 500" in str(raised.value)
    assert "secret upstream detail" not in str(raised.value)


async def test_rejects_non_stream_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "matrix", "result": []},
            },
        )

    collector = LokiEvidenceCollector(
        loki_settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LokiCollectionError, match="log streams"):
        await collector.collect(incident())
