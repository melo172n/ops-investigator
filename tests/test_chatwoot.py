import httpx
import pytest

from app.core.config import Settings
from app.integrations.chatwoot import ChatwootClient, ChatwootError


async def no_sleep(_: float) -> None:
    return None


def enabled_settings(**overrides) -> Settings:
    values = {
        "zabbix_webhook_secret": "test-secret",
        "chatwoot_enabled": True,
        "chatwoot_url": "https://chatwoot.example.com",
        "chatwoot_api_token": "api-token",
        "chatwoot_account_id": 1,
        "chatwoot_operations_conversation_id": 2,
        "chatwoot_retry_base_delay_seconds": 0,
    }
    values.update(overrides)
    return Settings(**values)


async def test_retries_rate_limit_and_records_each_attempt() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(429, request=request)
        return httpx.Response(200, json={"id": 321}, request=request)

    client = ChatwootClient(
        enabled_settings(),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )

    result = await client.send_operations_message("alert content")

    assert requests == 2
    assert result.message_id == 321
    assert [attempt.status for attempt in result.attempts] == ["failed", "sent"]
    assert result.attempts[0].detail == "HTTP 429"


async def test_does_not_retry_non_transient_client_error() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(403, request=request)

    client = ChatwootClient(
        enabled_settings(),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )

    with pytest.raises(ChatwootError) as raised:
        await client.send_operations_message("alert content")

    assert requests == 1
    assert len(raised.value.attempts) == 1
    assert raised.value.attempts[0].detail == "HTTP 403"


async def test_confirms_ambiguous_delivery_before_retrying() -> None:
    post_requests = 0
    get_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_requests, get_requests
        if request.method == "POST":
            post_requests += 1
            return httpx.Response(500, request=request)

        get_requests += 1
        return httpx.Response(
            200,
            json={"payload": [{"id": 654, "content": "alert content"}]},
            request=request,
        )

    client = ChatwootClient(
        enabled_settings(),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )

    result = await client.send_operations_message("alert content")

    assert post_requests == 1
    assert get_requests == 1
    assert result.message_id == 654
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "sent"
    assert "confirmed" in (result.attempts[0].detail or "")


async def test_retries_ambiguous_failure_when_message_was_not_created() -> None:
    post_requests = 0
    get_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_requests, get_requests
        if request.method == "POST":
            post_requests += 1
            if post_requests == 1:
                return httpx.Response(503, request=request)
            return httpx.Response(200, json={"id": 987}, request=request)

        get_requests += 1
        return httpx.Response(200, json={"payload": []}, request=request)

    client = ChatwootClient(
        enabled_settings(),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )

    result = await client.send_operations_message("alert content")

    assert post_requests == 2
    assert get_requests == 1
    assert result.message_id == 987
    assert [attempt.status for attempt in result.attempts] == ["failed", "sent"]


async def test_aborts_ambiguous_retry_when_confirmation_is_unavailable() -> None:
    post_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_requests
        if request.method == "POST":
            post_requests += 1
            return httpx.Response(500, request=request)
        return httpx.Response(502, request=request)

    client = ChatwootClient(
        enabled_settings(),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )

    with pytest.raises(ChatwootError) as raised:
        await client.send_operations_message("alert content")

    assert post_requests == 1
    assert len(raised.value.attempts) == 1
    assert raised.value.attempts[0].status == "failed"


async def test_retries_connect_error_up_to_configured_limit() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        raise httpx.ConnectError("unavailable", request=request)

    client = ChatwootClient(
        enabled_settings(chatwoot_max_attempts=2),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )

    with pytest.raises(ChatwootError) as raised:
        await client.send_operations_message("alert content")

    assert requests == 2
    assert len(raised.value.attempts) == 2
    assert all(attempt.status == "failed" for attempt in raised.value.attempts)
